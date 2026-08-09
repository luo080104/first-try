# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝
店铺转链
  @sellerId	String	必须	店铺id
  @pid	String	必须	推广位id
  @relationId	String	非必须	渠道id
  @shopName	String	必须	店铺名称，用于返回淘口令
"""


class TbShopConvertReq(Request):
    url = 'dels/shop/convert'
    check_params = ['sellerId','pid','shopName']


    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, shopName,sellerId, pid, relationId=None):
        self.addParams('sellerId', sellerId)
        self.addParams('pid', pid)
        self.addParams('relationId', relationId)
        self.addParams('shopName', shopName)
