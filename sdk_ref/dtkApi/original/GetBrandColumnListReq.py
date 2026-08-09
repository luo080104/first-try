# -*- coding:utf8-*-
"""
品牌栏目
  @cid	Integer	必须	大淘客分类id
  @pageId	Integer	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Integer	必须	每页记录条数（每页记录最大支持50，如果参数大于50时取50作为每页记录条数）
"""
from dtkApi.apiRequest import Request


class GetBrandColumnListReq(Request):
    url = 'delanys/brand/get-column-list'
    check_params = ['cid','pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize, cid):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('cid', cid)

