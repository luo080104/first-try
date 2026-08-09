# -*- coding:utf8-*-

from dtkApi.apiRequest import Request


# 加了签名校验的默认请求
class DefaultReq(Request):
    url = ''
    method = "GET"

    # GET请求
    def getResponse(self):
        return self.request(self.method, api_url=self.url, args=self.params)

    def setParams(self, url, method="GET", params={}):
        self.url = url
        self.method = method
        self.params = params
