# -*- coding:utf8-*-

"""
热门活动
"""
from dtkApi.apiRequest import Request


class ActivityCatalogueReq(Request):
    url = 'goods/activity/catalogue'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self):
        pass
