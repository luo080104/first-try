# -*- coding:utf8-*-

"""
各大榜单
  @rankType	Number	必须	榜单类型，1.实时榜 2.全天榜 3.热推榜 4.复购榜 5.热词飙升榜 6.热词排行榜 7.综合热搜榜
  @cid	Number	非必须	大淘客一级类目id，仅对实时榜单、全天榜单有效
  @pageSize	Number	非必须	每页条数返回条数（支持10,20.50，默认返回20条）
  @pageId	String	非必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）。超过200条，分页返回为空

"""
from dtkApi.apiRequest import Request


class RankingListReq(Request):
    url = 'goods/get-ranking-list'
    check_params = ['rankType']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, rankType,pageId=None, pageSize=None,cid=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('rankType', rankType)
        self.addParams('cid', cid)
