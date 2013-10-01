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

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


import unittest
from coapy.endpoint import *
import coapy.option


class TestEndpoint (unittest.TestCase):
    def testBasic6(self):
        ep = Endpoint(host='2001:db8:0::2:1')
        self.assertEqual(b'\x20\x01\x0d\xb8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x01',
                         ep.ip_addr)
        self.assertEqual('[2001:db8::2:1]', ep.uri_host)
        self.assertEqual(5683, ep.port)

    def testBasic4(self):
        ep = Endpoint(host='10.0.1.2', port=1234)
        self.assertEqual(b'\x0a\x00\x01\x02', ep.ip_addr)
        self.assertEqual('10.0.1.2', ep.uri_host)
        self.assertEqual(1234, ep.port)
        ep2 = Endpoint(host='10.0.1.2', port=1234)
        self.assertTrue(ep is ep2)

    def testNotAnInetAddr(self):
        naa = 'not an address'
        ep = Endpoint(naa)
        ep2 = Endpoint(naa)
        self.assertTrue(ep is ep2)
        self.assertTrue(ep.family is None)
        self.assertEqual(ep.ip_addr, naa.encode('utf-8'))
        self.assertEqual(ep.port, coapy.COAP_PORT)
        self.assertTrue(ep.security_mode is None)
        self.assertEqual(('not an address', coapy.COAP_PORT), ep.sockaddr)


class TestURLConversion (unittest.TestCase):
    def testB1(self):
        ep = Endpoint(host='2001:db8::2:1')
        url = 'coap://[2001:db8::2:1]/'
        opts = ep.uri_to_options(url)
        self.assertEqual(0, len(opts))
        durl = ep.uri_from_options(opts)
        self.assertEqual(url, durl)

    def testB2(self):
        ep = Endpoint(host='2001:db8::2:1')
        url = 'coap://example.net/'
        opts = ep.uri_to_options(url)
        self.assertEqual(1, len(opts))
        opt = opts[0]
        self.assertTrue(isinstance(opt, coapy.option.UriHost))
        self.assertEqual('example.net', opt.value)
        durl = ep.uri_from_options(opts)
        self.assertEqual(url, durl)

    def testB3(self):
        ep = Endpoint(host='2001:db8::2:1')
        url = 'coap://example.net/.well-known/core'
        opts = ep.uri_to_options(url)
        self.assertEqual(3, len(opts))
        opt = opts[0]
        self.assertTrue(isinstance(opt, coapy.option.UriHost))
        self.assertEqual('example.net', opt.value)
        opt = opts[1]
        self.assertTrue(isinstance(opt, coapy.option.UriPath))
        self.assertEqual('.well-known', opt.value)
        opt = opts[2]
        self.assertTrue(isinstance(opt, coapy.option.UriPath))
        self.assertEqual('core', opt.value)
        durl = ep.uri_from_options(opts)
        self.assertEqual(url, durl)

    def testB4(self):
        ep = Endpoint(host='2001:db8::2:1')
        url = 'coap://xn--18j4d.example/%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1%E3%81%AF'
        opts = ep.uri_to_options(url)
        self.assertEqual(2, len(opts))
        opt = opts[0]
        self.assertTrue(isinstance(opt, coapy.option.UriHost))
        self.assertEqual('xn--18j4d.example', opt.value)
        opt = opts[1]
        self.assertTrue(isinstance(opt, coapy.option.UriPath))
        self.assertEqual('こんにちは', opt.value)
        durl = ep.uri_from_options(opts)
        self.assertEqual(url, durl)

    def testB5(self):
        ep = Endpoint(host='198.51.100.1', port=61616)
        opts = (coapy.option.UriPath(''),
                coapy.option.UriPath('/'),
                coapy.option.UriPath(''),
                coapy.option.UriPath(''),
                coapy.option.UriQuery('//'),
                coapy.option.UriQuery('?&'))
        uri = ep.uri_from_options(opts)
        self.assertEqual('coap://198.51.100.1:61616//%2F//?%2F%2F&?%26', uri)
        uopts = ep.uri_to_options(uri)
        self.assertEqual(len(opts), len(uopts))
        for i in xrange(len(opts)):
            self.assertEqual(type(opts[i]), type(uopts[i]))
            self.assertEqual(opts[i].value, uopts[i].value)


if __name__ == '__main__':
    unittest.main()