# -*- coding:utf8-*-
"""
商品历史券后价
  @id String 必须 在大淘客的在线商品id（已下架的商品id不支持）
  @goodsId String 非必须 淘宝商品id
"""
from dtkApi.apiRequest import Request


class GoodspriceTrendReq(Request):
    url = 'goods/price-trend'
    check_params = ['id']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, id,goodsId=None):
        self.addParams('id', id)
        self.addParams('goodsId', goodsId)
