# -*- coding: utf-8 -*-
# Copyright 2013, Peter A. Bigot
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain a
# copy of the License at:
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""
    ************
    coapy.option
    ************

    :copyright: Copyright 2013, Peter A. Bigot
    :license: Apache-2.0
"""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


import coapy
import struct
import unicodedata


class OptionError (coapy.InfrastructureError):
    pass


class OptionRegistryConflictError (OptionError):
    """Exception raised when option numbers collide.

    CoAPy requires that each subclass of :py:class:`UrOption` has a
    unique option number, enforced by registering the
    subclass when its type is defined.  Attempts to use the same
    number for multiple options produce this exception.
    """
    pass


class InvalidOptionTypeError (OptionError):
    """Exception raised when an option is incorrectly defined.

    Each subclass of :py:class:`UrOption` must override
    :py:attr:`UrOption.number` with the integer option number,
    and :py:attr:`UrOption.format` with the type of the option.
    Failure to do so will cause this exception to be raised.
    """
    pass


class OptionValueLengthError (OptionError):
    pass


class OptionDecodeError (OptionError):
    pass


class UnrecognizedCriticalOptionError (OptionError):
    pass


class InvalidOptionError (OptionError):
    pass


class InvalidRequestOptionError (InvalidOptionError):
    pass


class InvalidResponseOptionError (InvalidOptionError):
    pass


class _format_base (object):
    """Abstract base for typed option value formatters.

    CoAP options encode values as byte sequences in one of several
    formats including:

    * :class:`format_empty` for no value
    * :class:`format_opaque` for uninterpreted byte sequences
    * :class:`format_uint` for variable-length unsigned integers
    * :class:`format_string` for Unicode text in Net-Unicode form
      (:rfc:`5198`).

    *max_length* is the maximum length of the packed representation in
    octets.  *min_length* is the minimum length of the packed
    representation in octets.
    """
    def _min_length(self):
        """The minimum acceptable length of the packed representation,
        in octets.  This is a read-only property."""
        return self.__min_length
    min_length = property(_min_length)

    def _max_length(self):
        """The maximum acceptable length of the packed representation,
        in octets.  This is a read-only property."""
        return self.__max_length
    max_length = property(_max_length)

    def _unpacked_type(self):
        """The Python type used for unpacked values.  This is a
        read-only property."""
        return self._UnpackedType
    unpacked_type = property(_unpacked_type)

    def __init__(self, max_length, min_length):
        self.__max_length = max_length
        self.__min_length = min_length

    def to_packed(self, value):
        """Convert *value* to packed form.

        If *value* is not an instance of :attr:`unpacked_type` then
        :exc:`ValueError` will be raised with *value* as an argument.

        The return value is a :class:`bytes` object with a length
        between :attr:`min_length` and :attr:`max_length`.  If *value*
        results in a packed format that is not within these bounds,
        :exc:`OptionValueLengthError` will be raised with *value* as
        an argument.
        """
        if not isinstance(value, self.unpacked_type):
            raise ValueError(value)
        pv = self._to_packed(value)
        if (len(pv) < self.min_length) or (self.max_length < len(pv)):
            raise OptionValueLengthError(value)
        return pv

    def _to_packed(self, value):
        """'Virtual' method implemented by subclasses to do
        type-specific packing.  The subclass implementation may assume
        *value* is of type :attr:`unpacked_type` and that the length
        constraints on the packed representation will be checked by
        :method:`to_packed`.
        """
        raise NotImplementedError

    def from_packed(self, packed):
        """Convert *packed* to its unpacked form.

        If *packed* is not an instance of :class:`bytes` then
        :exc:`ValueError` will be raised with *packed* as an argument.

        If the length of *packed* is not between :attr:`min_length`
        and :attr:`max_length` (both inclusive) then
        :exc:`OptionValueLengthError` will be raised with *packed* as
        an argument.

        Otherwise the value is unpacked and a corresponding instance
        of :attr:`unpacked_type` is returned.
        """
        if not isinstance(packed, bytes):
            raise ValueError(packed)
        if (len(packed) < self.min_length) or (self.max_length < len(packed)):
            raise OptionValueLengthError(packed)
        return self._from_packed(packed)

    def _from_packed(self, value):
        """'Virtual' method implemented by subclasses to do
        type-specific unpacking.  The subclass implementation may
        assume *value* is of type :attr:`bytes` and that the length
        constraints on the packed representation have been checked.
        It must return an instance of :attr:`unpacked_type`.
        """
        raise NotImplementedError


class format_empty (_format_base):
    """Support options with no value.

    The only acceptable value is a zero-length byte string.  This is
    both the packed and unpacked value.
    """

    _UnpackedType = bytes

    def __init__(self):
        super(format_empty, self).__init__(0, 0)

    def _to_packed(self, value):
        return value

    def _from_packed(self, value):
        return value


class format_opaque (_format_base):
    """Support options with opaque values.

    Unpacked values are instances of :class:`bytes`, and packing and
    unpacking is an identity operation.
    """

    _UnpackedType = bytes

    def __init__(self, max_length, min_length=0):
        super(format_opaque, self).__init__(max_length, min_length)

    def _to_packed(self, value):
        return value

    def _from_packed(self, value):
        return value


class format_uint (_format_base):
    """Supports options with variable-length unsigned integer values.
    *max_length* is the maximum number of octets in the packed format.
    The implicit *min_length* is always zero.

    Unpacked values are instances of :class:`int`.  The packed value is
    big-endian in a :class:`bytes` string with all zero-valued leading
    bytes removed.  Thus the packed representation of zero is an empty
    string.

    Per the CoAP specification packed values with leading NUL bytes
    will decode correctly; however, they are still subject to
    validation against :attr:`max_length`.
    """

    _UnpackedType = int

    def __init__(self, max_length):
        super(format_uint, self).__init__(max_length, 0)

    def _to_packed(self, value):
        if 0 == value:
            return b''
        pv = struct.pack(str('!Q'), value)
        for i in xrange(len(pv)):
            if ord(pv[i]) != 0:
                break
        return pv[i:]

    def _from_packed(self, data):
        value = 0
        for i in xrange(len(data)):
            value = (value * 256) + ord(data[i])
        return value

    def option_encoding(self, value):
        if (not isinstance(value, int)) or (0 > value):
            raise ValueError(value)
        if value < 13:
            ov = value
            ovx = b''
        elif value < 269:
            ov = 13
            ovx = self.to_packed(value - 13)
            while len(ovx) < 1:
                ovx = b'\x00' + ovx
        else:
            ov = 14
            ovx = self.to_packed(value - 269)
            while len(ovx) < 2:
                ovx = b'\x00' + ovx
        return (ov, ovx)

    def option_decoding(self, ov, data):
        if 15 <= ov:
            raise ValueError(ov)
        if 14 == ov:
            return (269 + self.from_packed(data[:2]), data[2:])
        if 13 == ov:
            return (13 + self.from_packed(data[:1]), data[1:])
        return (ov, data)


class format_string (_format_base):
    """Supports options with text values.

    Unpacked values are Python Unicode (text) strings.  Packed values
    are in Net-Unicode form (:rfc:`5198`).  Note that, as usual, the
    *max_length* and *min_length* attributes apply to the packed
    representation, which for non-ASCII text may be longer than the
    unpacked representation.
    """

    _UnpackedType = unicode

    def __init__(self, max_length, min_length=0):
        super(format_string, self).__init__(max_length, min_length)

    def _to_packed(self, value):
        # At first blush, this is Net-Unicode.
        rv = unicodedata.normalize('NFC', value).encode('utf-8')
        return rv

    def _from_packed(self, value):
        rv = value.decode('utf-8')
        return rv


_OptionRegistry = {}


# Internal function used to register option classes as their
# definitions are processed by Python.
def _register_option(option_class):
    if not issubclass(option_class, UrOption):
        raise InvalidOptionTypeError(option_class)
    if not isinstance(option_class.number, int):
        raise InvalidOptionTypeError(option_class)
    if not ((0 <= option_class.number) and (option_class.number <= 65535)):
        raise InvalidOptionTypeError(option_class)
    if not isinstance(option_class.format, _format_base):
        raise InvalidOptionTypeError(option_class)
    if option_class.number in _OptionRegistry:
        raise OptionRegistryConflictError(option_class)
    _OptionRegistry[option_class.number] = option_class
    return option_class


def find_option(number):
    """Look up an option by number.

    Returns the :py:class:`UrOption` subclass registered for *number*,
    or ``None`` if no such option has been registered.
    """
    return _OptionRegistry.get(number, None)


# Meta class used to enforce constraints on option types.  This serves
# several purposes:
#
# * It ensures that each subclass of UrOption properly provides both a
#   number and a format attribute;
#
# * It verifies that the values of these attributes are consistent with
#   the specification;
#
# * It rewrites the subclass so that those attributes are read-only in
#   both class and instance forms;
#
# * It registers each option class so that it can be looked up by
#   number.
#
# The concepts in this approach derive from:
# http://stackoverflow.com/questions/1735434/class-level-read-only-properties-in-python
class _MetaUrOption(type):

    # This class must do its work before UrOption has been added to
    # the module namespace.  Once that's been done this will be a
    # reference to it.
    __UrOption = None

    # The set of attributes in types that are to be made immutable if
    # the type provides a non-None value for the attribute.
    __ReadOnlyAttrs = ('number', 'repeatable', 'format')

    @classmethod
    def SetUrOption(cls, ur_option):
        cls.__UrOption = ur_option

    def __new__(cls, name, bases, namespace):
        # Provide a unique type that can hold the immutable class
        # number and format values.
        class UniqueUrOption (cls):
            pass

        do_register = (cls.__UrOption is not None) and namespace.get('_RegisterOption', True)

        # Only subclasses of UrOption have read-only attributes.  Make
        # those attributes immutable at both the class and instance
        # levels.
        if (cls.__UrOption is not None):
            for n in cls.__ReadOnlyAttrs:
                v = namespace.get(n, None)
                if (v is not None) and not isinstance(v, property):
                    mp = property(lambda self_or_cls, _v=v: _v)
                    namespace[n] = mp
                    setattr(UniqueUrOption, n, mp)

        # Create the subclass type, and register it if it's complete
        # (and not UrOption).
        mcls = type.__new__(UniqueUrOption, name, bases, namespace)
        if do_register:
            _register_option(mcls)

        return mcls


def is_critical_option(number):
    """Return ``True`` iff *number* identifies a critical option.

    A *critical* option is one that must be understood by the endpoint
    processing the message.  This is indicated by bit 0 (0x01) of the
    *number* being set.
    """
    return number & 1


def is_unsafe_option(number):
    """Return ``True`` iff the option number identifies an unsafe option.

    An *unsafe* option is one that must be recognized by a proxy in
    order to safely forward (or cache) the message.  This is indicated
    by bit 1 (0x02) of the *number* being set."""
    return number & 2


def is_no_cache_key_option(number):
    """Return ``True`` iff the option number identifies a NoCacheKey option.

    A *NoCacheKey* option is one for which the value of the option
    does not contribute the key that identifies a matching value in a
    cache.  This is encoded in bits 1 through 5 of the *number*.

    """
    return (0x1c == (number & 0x1e))


class UrOption (object):
    """Abstract base for CoAP options.

    """

    __metaclass__ = _MetaUrOption

    number = None
    """The option number.

    An unsigned integer in the range 0..65535.  This is an
    IANA-registered value with the following policies
    (:rfc:`5226`):

    ============   ========
    Option Range   Policy
    ============   ========
        0..255     IETF Review or IESG Approval
      256..2047    Specification Required
     2048..64999   Designated Expert
    65000..65535   Reserved for experiments
    ============   ========

    The attribute is read-only.  Each subclass of :py:class:`UrOption`
    is registered during its definition; :py:exc:`InvalidOptionType`
    will be raised if multiple options with the same number are
    defined.
    """

    repeatable = None
    """A tuple ``(request, response)`` indicating allowed
    cardinality of the option in requests and responses, respectively.

    The value of *request* and *response* is ``True`` if the option
    may appear multiple times in the corresponding message, ``False``
    if it must appear only once, and ``None`` if it may not appear at
    all.
    """

    format = None

    def is_critical(self):
        return is_critical_option(self.number)

    def is_unsafe(self):
        return is_unsafe_option(self.number)

    def is_no_cache_key(self):
        return is_no_cache_key_option(self.number)

    def valid_in_request(self):
        return self.repeatable[0] is not None

    def valid_multiple_in_request(self):
        return self.repeatable[0] is True

    def valid_in_response(self):
        return self.repeatable[1] is not None

    def valid_multiple_in_response(self):
        return self.repeatable[1] is True

    def __init__(self, unpacked_value=None, packed_value=None):
        super(UrOption, self).__init__()
        if unpacked_value is not None:
            self._set_value(unpacked_value)
        elif packed_value is not None:
            self.__value = self.format.from_packed(packed_value)
        else:
            self.__value = None

    def _set_value(self, unpacked_value):
        self.__value = self.format.from_packed(self.format.to_packed(unpacked_value))

    def _get_value(self):
        return self.__value

    value = property(_get_value, _set_value)

    def packed_value(self):
        return self.format.to_packed(self.value)


# Register the UrOption so subclasses can
_MetaUrOption.SetUrOption(UrOption)

# A utility instance used to encode and decode variable-length
# integers in options, which comprise a 4-bit code with zero to two
# bytes of offset.
_optionint_helper = format_uint(2)


def encode_options(options, is_request):
    last_number = 0
    packed = []
    options = sorted(options, key=lambda _o: _o.number)
    for opt in options:
        delta = opt.number - last_number
        if (is_request
            and ((not opt.valid_in_request())
                 or ((0 == delta) and not opt.valid_multiple_in_request()))):
            raise InvalidRequestOptionError(opt)
        elif ((not is_request)
              and ((not opt.valid_in_response())
                   or ((0 == delta) and not opt.valid_multiple_in_response()))):
            raise InvalidResponseOptionError(opt)
        last_number = opt.number
        pvalue = opt.packed_value()
        (od, odx) = _optionint_helper.option_encoding(delta)
        (ol, olx) = _optionint_helper.option_encoding(len(pvalue))
        encoded = struct.pack(str('B'), (od << 4) | ol)
        encoded += odx + olx + pvalue
        packed.append(encoded)
    return b''.join(packed)


def _decode_one_option(data):
    (odl,) = struct.unpack(str('!B'), data[0])
    if 0xFF == odl:
        return (None, None, data)
    data = data[1:]
    od = (odl >> 4)
    ol = (odl & 0x0F)
    if (15 == od) or (15 == ol):
        raise OptionDecodeError(data)
    (delta, data) = _optionint_helper.option_decoding(od, data)
    (length, data) = _optionint_helper.option_decoding(ol, data)
    return (delta, length, data)


def decode_options(data, is_request):
    idx = 0
    option_number = 0
    options = []
    while 0 < len(data):
        (delta, length, data) = _decode_one_option(data)
        if delta is None:
            break
        packed = data[:length]
        data = data[length:]
        option_number += delta
        option_type = find_option(option_number)
        if option_type is None:
            opt = UnknownOption(option_number, packed_value=packed)
        else:
            opt = option_type(packed_value=packed)
        options.append(opt)
    return (options, data)


class UnknownOption (UrOption):
    _RegisterOption = False
    repeatable = (True, True)
    format = format_opaque(1034)

    def _get_number(self):
        return self.__number
    number = property(_get_number)

    def __init__(self, number, unpacked_value=None, packed_value=None):
        if not (isinstance(number, int) and (0 <= number) and (number <= 65535)):
            raise ValueError('invalid option number')
        option = find_option(number)
        if option is not None:
            raise ValueError('conflicting option number', option)
        self.__number = number
        super(UnknownOption, self).__init__(unpacked_value=unpacked_value,
                                            packed_value=packed_value)


class IfMatch (UrOption):
    number = 1
    repeatable = (True, None)
    format = format_opaque(8)


class UriHost (UrOption):
    number = 3
    repeatable = (False, None)
    format = format_string(255, min_length=1)


class ETag (UrOption):
    number = 4
    repeatable = (True, False)
    format = format_opaque(8, min_length=1)


class IfNoneMatch (UrOption):
    number = 5
    repeatable = (False, None)
    format = format_empty()

    def __init__(self, unpacked_value=None, packed_value=None):
        if (unpacked_value is None) and (packed_value is None):
            unpacked_value = b''
        super(IfNoneMatch, self).__init__(unpacked_value=unpacked_value,
                                          packed_value=packed_value)


class UriPort (UrOption):
    number = 7
    repeatable = (False, None)
    format = format_uint(2)


class LocationPath (UrOption):
    number = 8
    repeatable = (None, True)
    format = format_string(255)


class UriPath (UrOption):
    number = 11
    repeatable = (True, None)
    format = format_string(255)


class ContentFormat (UrOption):
    number = 12
    repeatable = (False, False)
    format = format_uint(2)


class MaxAge (UrOption):
    number = 14
    repeatable = (None, False)
    format = format_uint(4)


class UriQuery (UrOption):
    number = 15
    repeatable = (True, None)
    format = format_string(255)


class Accept (UrOption):
    number = 17
    repeatable = (False, None)
    format = format_uint(2)


class LocationQuery (UrOption):
    number = 20
    repeatable = (None, True)
    format = format_string(255)


class ProxyUri (UrOption):
    number = 35
    repeatable = (False, None)
    format = format_string(1034, min_length=1)


class ProxyScheme (UrOption):
    number = 39
    repeatable = (False, None)
    format = format_string(255, min_length=1)


class Size1 (UrOption):
    number = 60
    repeatable = (False, False)
    format = format_uint(4)
