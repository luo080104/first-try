# -*- coding:utf8-*-

"""
首单礼金商品
@pageSize Number 必须 每页返回条数，每页条数支持输入10,20，50,100,200
@pageId String 必须 分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
@cids String 非必须 大淘客的一级分类id，如果需要传多个，以英文逗号相隔，如：”1,2,3”。1 -女装，2 -母婴，3 -美妆，4 -居家日用，5 -鞋品，6 -美食，7 -文娱车品，8 -数码家电，9 -男装，10 -内衣，11 -箱包，12 -配饰，13 -户外运动，14 -家装家纺
@sort String 非必须 排序方式，默认为0，0-综合排序，1-商品上架时间从高到低，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高
@keyWord String 非必须 输入关键词搜索(新增字段)
@goodsType Number 非必须 商品类型1表示大淘客商品2表示联盟商品。默认为1 （2020.11.4新增字段）
"""

from dtkApi.apiRequest import Request


class FirstOrderGiftMoneyReq(Request):
    url = 'goods/first-order-gift-money'
    check_params = ['pageId', 'pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize, cids=None, sort=None, keyWord=None,goodsType=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('cids', cids)
        self.addParams('sort', sort)
        self.addParams('keyWord', keyWord)
        self.addParams('goodsType', goodsType)
