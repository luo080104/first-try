# -*- coding:utf8-*-

"""
9.9包邮精选
  @pageSize	Number	必须	每页条数：默认为20，最大值100
  @pageId	String	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @nineCid	String	必须	9.9精选的类目id，分类id请求详情：-1-精选，1 -5.9元区，2 -9.9元区，3 -19.9元区（调整字段）

"""
from dtkApi.apiRequest import Request


class OpGoodsListReq(Request):
    url = 'nine/op-goods-list'
    check_params = ['pageId','pageSize','nineCid']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, nineCid,pageId, pageSize):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('nineCid', nineCid)
