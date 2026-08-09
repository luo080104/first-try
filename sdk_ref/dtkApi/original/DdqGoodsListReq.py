# -*- coding:utf8-*-
"""
咚咚抢
  @roundTime String 非必须 默认为当前场次，场次时间输入方式：yyyy-mm-dd hh:mm:ss

"""
from dtkApi.apiRequest import Request


class DdqGoodsListReq(Request):
    url = 'category/ddq-goods-list'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, roundTime=None):
        self.addParams('roundTime', roundTime)