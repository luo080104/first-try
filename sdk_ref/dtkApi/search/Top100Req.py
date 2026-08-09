# -*- coding:utf8-*-

"""
热搜榜
  @type Integer  非必须  1：买家热搜榜（默认）、2：淘客热搜榜
"""
from dtkApi.apiRequest import Request


class Top100Req(Request):
    url = 'category/get-top100'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,type=None):
        self.addParams('type', type)