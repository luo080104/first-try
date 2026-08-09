# -*- coding:utf8-*-

"""
京东商品详情
 @skuIds String 必须 商品skuId，多个使用逗号分隔，最多支持10个skuId同时查询（需使用半角状态下的逗号）
"""
from dtkApi.apiRequest import Request


class JdGoodsDetaillReq(Request):
    url = 'dels/jd/goods/get-details'
    check_params = ['skuIds']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)
    def setParams(self, skuIds):
        self.addParams('skuIds', skuIds)
