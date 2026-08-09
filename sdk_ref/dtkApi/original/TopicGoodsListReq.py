# -*- coding:utf8-*-
"""
专题商品
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口第一次返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入库商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  @pageSize	Number	非必须	每页条数，默认为100，大于100按100处理
  @topicId	Number	必须	专辑id，通过精选专辑API获取的活动id

"""
from dtkApi.apiRequest import Request


class TopicGoodsListReq(Request):
    url = 'goods/topic/goods-list'
    check_params = ['pageId','topicId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId,topicId, pageSize=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('topicId', topicId)