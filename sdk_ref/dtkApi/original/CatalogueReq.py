# -*- coding:utf8-*-
"""
精选专题
"""

from dtkApi.apiRequest import Request


class CatalogueReq(Request):
    url = 'goods/topic/catalogue'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self):
        pass
