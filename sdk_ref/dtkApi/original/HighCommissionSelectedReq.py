# -*- coding:utf8-*-
"""
高佣精选
  @pageId	String	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Integer	必须	每页返回条数，每页条数支持输入10,20，50,100。
  @cid Integer 非必须 大淘客的一级分类id
  @sort Integer 非必须 排序：默认按佣金比例降序1-按销量降序，2-按销量升序，3-按佣金比例降序，4-按佣金比例升序。
"""
from dtkApi.apiRequest import Request


class HighCommissionSelectedReq(Request):
    url = 'goods/singlePage/list-height-commission'
    check_params = ['pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize=None, sort=None, cid=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('sort', sort)
        self.addParams('cid', cid)