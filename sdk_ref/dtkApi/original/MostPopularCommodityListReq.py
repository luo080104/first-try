# -*- coding:utf8-*-
"""
爆品预告商品合集
  @type Integer  非必须  时间段1、昨天0点，2、昨天10点，3、今天0点，4、今天10点（默认），5、明天0点，6、明天10点
"""
from dtkApi.apiRequest import Request


class MostPopularCommodityListReq(Request):
    url = 'goods/get-hot-advance'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, type=None):
        self.addParams('type', type)