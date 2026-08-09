# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
拼多多商品类目查询
 @parentId Integer 非必须 父级类目ID（一级父类目为0）
"""


class PddGoodsCategoryReq(Request):
    url = 'dels/pdd/category/search'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, parentId=None):
        self.addParams('parentId', parentId)
