# -*- coding:utf8-*-
"""
京东商品历史券后价
  @skuId	Number	必须	商品id
  @offsetDays	Integer	 非必须	查询时间类型：默认30天，可以1-近7天，2-近30天，3-近60天
"""
from dtkApi.apiRequest import Request


class JdGoodspriceTrendReq(Request):
    url = 'dels/jd/stats/goods/historyPriceRecords'
    check_params = ['skuId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, skuId, offsetDays=None):
        self.addParams('skuId', skuId)
        self.addParams('offsetDays', offsetDays)
