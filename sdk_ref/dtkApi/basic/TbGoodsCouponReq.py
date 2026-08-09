# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝商品
优惠券查询
 @content String 必须  二合一链接，淘口令，或同时输入商品+优惠券链接
"""


class TbGoodsCouponReq(Request):
    url = 'dels/taobao/kit/coupon/get-coupon-info'
    check_params = ['content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, content):
        self.addParams('content', content)