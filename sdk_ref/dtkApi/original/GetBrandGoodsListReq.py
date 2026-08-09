# -*- coding:utf8-*-
"""
单个品牌详情
  @brandId	String	必须	品牌id
  @pageId	Integer	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……） 第一页时会携带品牌信息数据
  @pageSize	Integer	必须	每页记录条数（每页支持最大记录条数100）
"""
from dtkApi.apiRequest import Request


class GetBrandGoodsListReq(Request):
    url = 'delanys/brand/get-goods-list'
    check_params = ['brandId','pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize, brandId):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('cid', brandId)
