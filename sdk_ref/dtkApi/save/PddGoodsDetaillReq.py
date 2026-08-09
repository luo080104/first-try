# -*- coding:utf8-*-

"""
拼多多商品详情
  goodsSign	String	必须	商品goodsSign，支持通过goodsSign查询商品。goodsSign是加密后的goodsId, goodsId已下线，请使用goodsSign来替代。使用说明：https://jinbao.pinduoduo.com/qa-system?questionId=252
  searchId	Integer	非必须	搜索id，建议填写，可提高收益。可通过pdd.ddk.goods.recommend.get、pdd.ddk.goods.search、pdd.ddk.top.goods.list.query等接口获取
  goodsImgType	Integer	非必须	商品主图类型：1-场景图，2-白底图，默认为0

"""
from dtkApi.apiRequest import Request


class PddGoodsDetaillReq(Request):
    url = 'dels/pdd/goods/detail'
    check_params = ['goodsSign']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, goodsSign, searchId=None, goodsImgType=None):
        self.addParams('goodsSign', goodsSign)
        self.addParams('searchId', searchId)
        self.addParams('goodsImgType', goodsImgType)

