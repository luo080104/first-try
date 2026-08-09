# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝商品
超值买返商品转链
 @goodsId	String	必须	商品id
 @title	String	必须	商品标题
 @pid	String	非必须	淘宝联盟pid
 @relationId	String	非必须	渠道id
 @couponId	String	非必须	优惠券id
"""


class CzmfGoodsLinkReq(Request):
    url = 'dels/taobao/kit/turnLink/czmf'
    check_params = ['goodsId','title']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, goodsId, title, pid=None, relationId=None, couponId=None):
        self.addParams('goodsId', goodsId)
        self.addParams('title', title)
        self.addParams('pid', pid)
        self.addParams('relationId', relationId)
        self.addParams('couponId', couponId)