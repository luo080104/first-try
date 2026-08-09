# -*- coding:utf8-*-

"""
每日半价
  @sessions String 必须 默认为当前时间场次，场次输入格式，例如02、08、12、16（具体可以参考返回参数中的：hpdTime）
"""
from dtkApi.apiRequest import Request


class GetHalfPriceDayReq(Request):
    url = 'goods/get-half-price-day'
    check_params = ['sessions']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, sessions):
        self.addParams('sessions', sessions)