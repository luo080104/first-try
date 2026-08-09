# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东商品批量转链
 @unionId	Long	必须	推客的联盟ID
 @positionId	Long	非必须	新增推广位id （若无subUnionId权限，可入参该参数用来确定不同用户下单情况）
 @childPid	String	非必须	联盟子推客身份标识（不能传入接口调用者自己的pid）
 @subUnionId	String	非必须	子渠道标识，您可自定义传入字母、数字或下划线，最多支持80个字符，该参数会在订单行查询接口中展示，需要有权限才可使用
 @content	String	必须	待转链京东商品物料地址(需要urlencode，优惠券无法进行转链，无法转链的地址会按照原数据返回)
"""


class JdGoodsBatchLinkReq(Request):
    url = 'dels/jd/kit/content/promotion-union-convert'
    check_params = ['unionId','content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, unionId,content, positionId=None, childPid=None, subUnionId=None):
        self.addParams('unionId', unionId)
        self.addParams('positionId', positionId)
        self.addParams('childPid', childPid)
        self.addParams('subUnionId', subUnionId)
        self.addParams('content', content)
