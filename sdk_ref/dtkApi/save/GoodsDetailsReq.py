# -*- coding:utf8-*-

"""
单品详情
  @id	Number	必须	大淘客商品id，请求时id或goodsId必填其中一个，若均填写，将优先查找当前单品id
  @goodsId	String	非必须	淘宝商品id，id或goodsId必填其中一个，若均填写，将优先查找当前单品id
"""
from dtkApi.apiRequest import Request


class GoodsDetailsReq(Request):
    url = 'goods/get-goods-details'
    check_params = ['id']
    other_params = ['goodsId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params) or self.check_args(self.params, self.other_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, id=None, goodsId=None):
        self.addParams('id', id)
        self.addParams('goodsId', goodsId)
