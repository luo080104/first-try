# -*- coding:utf8-*-

"""
细分类目榜
  @subdivisionId	Integer	必须	细分类目榜分类id（从商品详情获取）
"""
from dtkApi.apiRequest import Request


class SubdivisionCategoryRankReq(Request):
    url = 'subdivision/get-rank-list'
    check_params = ['subdivisionId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, subdivisionId):
        self.addParams('subdivisionId', subdivisionId)
