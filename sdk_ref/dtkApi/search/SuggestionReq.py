# -*- coding:utf8-*-

"""
联想词
  @keyWords	String	必须	关键词
  @type	Number	必须	当前搜索API类型：1.大淘客搜索 2.联盟搜索 3.超级搜索

"""
from dtkApi.apiRequest import Request


class SuggestionReq(Request):
    url = 'goods/search-suggestion'
    check_params = ['keyWords','type']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,keyWords,type):
        self.addParams('keyWords', keyWords)
        self.addParams('type', type)
