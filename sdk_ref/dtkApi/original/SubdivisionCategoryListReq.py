# -*- coding:utf8-*-

"""
细分类目合集
  @pageId	Integer	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Integer	必须	每页条数，默认20，最大100条
  @cid	Integer	必须	大淘客一级分类ID：1 -女装，2 -母婴，3 -美妆，4 -居家日用，5 -鞋品，6 -美食，7 -文娱车品，8 -数码家电，9 -男装，10 -内衣，11 -箱包，12 -配饰，13 -户外运动，14 -家装家纺
"""
from dtkApi.apiRequest import Request


class SubdivisionCategoryListReq(Request):
    url = 'subdivision/get-list'
    check_params = ['pageId','pageSize','cid']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, cid,pageId, pageSize):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('cid', cid)
