# -*- coding:utf8-*-
"""
轮播图
"""
from dtkApi.apiRequest import Request


class CarouselMapResponseReq(Request):
    url = 'goods/topic/carouse-list'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self):
        pass
