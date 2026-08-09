# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东商品类目查询
 @parentId Integer 非必须 父级类目ID（一级父类目为0）
 @level Integer 非必须 类目级别（类目级别 0，1，2 代表一、二、三级类目）
"""


class JdGoodsCategoryReq(Request):
    url = 'dels/jd/category/search'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, parentId=None,level=None):
        self.addParams('parentId', parentId)
        self.addParams('level', level)
