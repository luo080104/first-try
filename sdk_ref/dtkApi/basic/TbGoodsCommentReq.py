# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝商品
商品评论
  @id	Integer	必须	大淘客商品id（id和goodsid其中一个必填）
  @goodsId	String	非必须	淘宝商品id（id和goodsid其中一个必填）
  @type	Integer	非必须	默认：0-全部 评论类型：0-全部；1-含图；2-含视频；
  @sort	Integer	非必须	排序方式 0-按热度排序 1-按最新添加排序 默认为0
  @haopingType	Integer	非必须	评论类型 0-全部 1-去掉默认好评 默认为0(2020/12/30新增字段)

"""


class TbGoodsCommentReq(Request):
    url = 'comment/get-comment-list'
    check_params = ['id']
    other_check_params = ['goodsId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params) or self.check_args(self.params, self.other_check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, id, goodsId=None, type=None, sort=None, haopingType=None):
        self.addParams('id', id)
        self.addParams('goodsId', goodsId)
        self.addParams('type', type)
        self.addParams('sort', sort)
        self.addParams('haopingType', haopingType)