"""Netlink Attributes (netlink/attr.h) (lib/attr.c).
https://github.com/thom311/libnl/blob/libnl3_2_25/include/netlink/attr.h
https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation version 2.1
of the License.
"""

import ctypes
import logging

from libnl.errno_ import NLE_RANGE, NLE_INVAL
from libnl.linux_private.netlink import nlattr, NLA_ALIGN, NLA_TYPE_MASK, NLA_HDRLEN, NLA_F_NESTED
from libnl.netlink_private.netlink import BUG

_LOGGER = logging.getLogger(__name__)
NLA_UNSPEC = 0  # Unspecified type, binary data chunk.
NLA_U8 = 1  # 8 bit integer.
NLA_U16 = 2  # 16 bit integer.
NLA_U32 = 3  # 32 bit integer.
NLA_U64 = 4  # 64 bit integer.
NLA_STRING = 5  # NUL terminated character string.
NLA_FLAG = 6  # Flag.
NLA_MSECS = 7  # Micro seconds (64bit).
NLA_NESTED = 8  # Nested attributes.
NLA_TYPE_MAX = NLA_NESTED


class nla_policy(object):
    """Attribute validation policy
    https://github.com/thom311/libnl/blob/libnl3_2_25/include/netlink/attr.h#L60

    Instance variables:
    type_ -- type of attribute or NLA_UNSPEC (c_uint16).
    minlen -- minimal length of payload required (c_uint16).
    maxlen -- maximal length of payload allowed (c_uint16).
    """

    def __init__(self, type_=0, minlen=0, maxlen=0):
        self.type_ = type_
        self.minlen = minlen
        self.maxlen = maxlen

    def __repr__(self):
        answer = '<{0}.{1} type_={2} minlen={3} maxlen={4}>'.format(
            self.__class__.__module__,
            self.__class__.__name__,
            self.type_, self.minlen, self.maxlen,
        )
        return answer


def nla_type(nla):
    """Return type of the attribute.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L109

    Positional arguments:
    nla -- attribute.

    Returns:
    Type of attribute.
    """
    return nla.nla_type & NLA_TYPE_MASK


def nla_data(nla):
    """Return payload section.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L120

    Positional arguments:
    nla -- attribute.

    Returns:
    Pointer to start of payload section.
    """
    return nla.payload


def nla_len(nla):
    """Return length of the payload.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L131

    Positional arguments:
    nla -- attribute.

    Returns:
    Length of payload in bytes.
    """
    return int(nla.nla_len - NLA_HDRLEN)


def nla_ok(nla, remaining):
    """Check if the attribute header and payload can be accessed safely.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L148

    Verifies that the header and payload do not exceed the number of bytes left in the attribute stream. This function
    must be called before access the attribute header or payload when iterating over the attribute stream using
    nla_next().

    Positional arguments:
    nla -- attribute of any kind.
    remaining -- number of bytes remaining in attribute stream.

    Returns:
    True if the attribute can be accessed safely, False otherwise.
    """
    return remaining >= ctypes.sizeof(*nla) and ctypes.sizeof(*nla) <= nla.nla_len <= remaining


def nla_next(nla, remaining):
    """Return next attribute in a stream of attributes.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L171

    Calculates the offset to the next attribute based on the attribute given. The attribute provided is assumed to be
    accessible, the caller is responsible to use nla_ok() beforehand. The offset (length of specified attribute
    including padding) is then subtracted from the remaining bytes variable and a pointer to the next attribute is
    returned.

    nla_next() can be called as long as remaining is >0.

    Returns:
    Pointer to next attribute.
    """
    totlen = int(NLA_ALIGN(nla.nla_len))
    remaining.value -= totlen
    return ctypes.cast(ctypes.byref(nla, totlen), ctypes.POINTER(nlattr))


nla_attr_minlen = {i: 0 for i in range(NLA_TYPE_MAX + 1)}
nla_attr_minlen.update({  # https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L179
    NLA_U8: ctypes.sizeof(ctypes.c_uint8),
    NLA_U16: ctypes.sizeof(ctypes.c_uint16),
    NLA_U32: ctypes.sizeof(ctypes.c_uint32),
    NLA_U64: ctypes.sizeof(ctypes.c_uint64),
    NLA_STRING: 1,
    NLA_FLAG: 0,
})


def validate_nla(nla, maxtype, policy):
    """https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L188

    Positional arguments:
    nla -- nlattr class instance.
    maxtype -- integer.
    policy -- nla_policy class instance.

    Returns:
    0 on success or a negative error code.
    """
    minlen = 0
    type_ = nla_type(nla)
    if type_ < 0 or type_ > maxtype:
        return 0

    pt = policy[type_]
    if pt.type_ > NLA_TYPE_MAX:
        raise BUG

    if pt.minlen:
        minlen = pt.minlen
    elif pt.type_ != NLA_UNSPEC:
        minlen = nla_attr_minlen[pt.type_]

    if nla_len(nla) < minlen:
        return -NLE_RANGE

    if pt.maxlen and nla_len(nla) > pt.maxlen:
        return -NLE_RANGE

    if pt.type_ == NLA_STRING:
        data = nla_data(nla)
        if data[nla_len(nla) - 1] != 0:
            return -NLE_INVAL

    return 0


def nla_parse(tb, maxtype, head, policy):
    """Create attribute index based on a stream of attributes.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L242

    Iterates over the stream of attributes and stores an instance to each attribute in the `tb` dictionary using the
    attribute type as the key. Attribute with a type greater than the maximum type specified will be silently ignored in
    order to maintain backwards compatibility. If `policy` is not None, the attribute will be validated using the
    specified policy.

    Positional arguments:
    tb -- dictionary to be filled (maxtype+1 elements).
    maxtype -- maximum attribute type expected and accepted.
    head -- list of attributes.
    policy -- attribute validation policy.

    Returns:
    0 on success or a negative error code.
    """
    for nla in nla_for_each_attr(head):
        type_ = nla_type(nla)
        if type_ > maxtype:
            continue

        if policy:
            err = validate_nla(nla, maxtype, policy)
            if err < 0:
                return err

        if type_ in tb:
            _LOGGER.debug('Attribute of type %d found multiple times in message, previous attribute is being ignored.',
                          type_)
        tb[type_] = nla

    return 0


def nla_for_each_attr(head):
    """Iterate over a list of attributes.
    https://github.com/thom311/libnl/blob/libnl3_2_25/include/netlink/attr.h#L262

    Positional arguments:
    head -- list of attributes.

    Returns:
    Generator yielding nl_attr instances.
    """
    return (a for a in head if isinstance(a, nlattr))


def nla_find(attrs, attrtype):
    """Find a single attribute in a list of attributes.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L323

    Iterates over the stream of attributes and compares each type with the type specified. Returns the first attribute
    which matches the type.

    Positional arguments:
    attrs -- list of attributes or payload containing attributes.
    attrtype -- attribute type to look for.

    Returns:
    Attribute found or None.
    """
    for nla in nla_for_each_attr(attrs):
        if nla_type(nla) == attrtype:
            return nla
    return None


def nla_put(msg, attrtype, data):
    """Add a unspecific attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L497

    Copies the provided data into the message as payload of the attribute.

    Positional arguments:
    msg -- netlink message.
    attrtype -- attribute type.
    data -- data to be used as attribute payload.

    Returns:
    0
    """
    nla = nlattr(nla_type=attrtype, payload=data)
    msg.nm_nlh.payload.append(nla)
    if not data:
        return 0
    try:
        datalen = ctypes.sizeof(data)
    except TypeError:
        datalen = len(data)
    _LOGGER.debug('msg 0x%x: attr <0x%x> %d: Wrote %d bytes', id(msg), id(nla), nla.nla_type, datalen)
    return 0


def nla_put_u8(msg, attrtype, value):
    """Add 8 bit integer attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L563

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- numeric value to store as payload (int() or c_uint8()).

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, value if isinstance(value, ctypes.c_uint8) else ctypes.c_uint8(value)))


def nla_get_u8(nla):
    """Return value of 8 bit integer attribute as an int().
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L574

    Positional arguments:
    nla -- 8 bit integer attribute.

    Returns:
    Payload as an int().
    """
    if isinstance(nla.payload, ctypes.c_uint8):
        value = nla.payload.value
    else:
        value = ctypes.c_uint8.from_buffer(nla.payload).value
    return int(value)


def nla_put_u16(msg, attrtype, value):
    """Add 16 bit integer attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L588

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- numeric value to store as payload (int() or c_uint16()).

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, value if isinstance(value, ctypes.c_uint16) else ctypes.c_uint16(value)))


def nla_get_u16(nla):
    """Return value of 16 bit integer attribute as an int().
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L599

    Positional arguments:
    nla -- 16 bit integer attribute.

    Returns:
    Payload as an int().
    """
    if isinstance(nla.payload, ctypes.c_uint16):
        value = nla.payload.value
    else:
        value = ctypes.c_uint16.from_buffer(nla.payload).value
    return int(value)


def nla_put_u32(msg, attrtype, value):
    """Add 32 bit integer attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L613

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- numeric value to store as payload (int() or c_uint32()).

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, value if isinstance(value, ctypes.c_uint32) else ctypes.c_uint32(value)))


def nla_get_u32(nla):
    """Return value of 32 bit integer attribute as an int().
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L624

    Returns:
    Payload as an int().
    """
    if isinstance(nla.payload, ctypes.c_uint32):
        value = nla.payload.value
    else:
        value = ctypes.c_uint32.from_buffer(nla.payload).value
    return int(value)


def nla_put_u64(msg, attrtype, value):
    """Add 64 bit integer attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L638

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- numeric value to store as payload (int() or c_uint64()).

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, value if isinstance(value, ctypes.c_uint64) else ctypes.c_uint64(value)))


def nla_get_u64(nla):
    """Return value of 64 bit integer attribute as an int().
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L649

    Returns:
    Payload as an int().
    """
    if isinstance(nla.payload, ctypes.c_uint64):
        value = nla.payload.value
    else:
        value = ctypes.c_uint64.from_buffer(nla.payload).value
    return int(value)


def nla_put_string(msg, attrtype, value):
    """Add string attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L674

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- bytes() string value (e.g. bytes('Test'.encode('ascii'))).

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, value if value.endswith(b'\0') else value + b'\0'))


def nla_get_string(nla):
    """Return string attribute.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L685

    Returns:
    bytes() string value.
    """
    return nla.payload.rstrip(b'\0')


def nla_put_flag(msg, attrtype):
    """Add flag netlink attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L709

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.

    Returns:
    0
    """
    return int(nla_put(msg, attrtype, None))


def nla_get_flag(nla):
    """Return True if flag attribute is set.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L720

    Returns:
    True if flag is set, otherwise False.
    """
    return bool(nla)


def nla_put_msecs(msg, attrtype, value):
    """Add msecs attribute to netlink message.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L737

    Positional arguments:
    msg -- netlink message (nl_msg class instance).
    attrtype -- attribute type.
    value -- numeric msecs (int(), c_uint64(), or c_ulong()).

    Returns:
    0
    """
    if isinstance(value, ctypes.c_uint64):
        pass
    elif isinstance(value, ctypes.c_ulong):
        value = ctypes.c_uint64(value.value)
    else:
        value = ctypes.c_uint64(value)
    return int(nla_put_u64(msg, attrtype, value))


def nla_get_msecs(nla):
    """Return value of msecs attribute as an int().
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L748

    Returns:
    Payload as an int().
    """
    return nla_get_u64(nla)


def nla_is_nested(attr):
    """Return True if attribute has NLA_F_NESTED flag set.
    https://github.com/thom311/libnl/blob/libnl3_2_25/lib/attr.c#L897

    Positional arguments:
    attr -- netlink attribute (nlattr class instance).

    Returns:
    True if attribute has NLA_F_NESTED flag set, otherwise False.
    """
    return not not attr.nla_type & NLA_F_NESTED
