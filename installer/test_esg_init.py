#!/usr/bin/local/env python

import unittest
import esg_init
#import esg_version_manager


class Test_ESG_Init(unittest.TestCase):
    def test_init(self):
        for x in esg_init.init():
            try:
                self.assertTrue(x in ["apache_frontend_version", "cdat_version"], True)
            except TypeError, e:
                print "error:", e
                print "x:", x

if __name__ == '__main__':
    unittest.main()
