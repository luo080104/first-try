# -*- coding:utf8-*-

"""官方活动会场转链
@promotionSceneId：string  必须 联盟官方活动ID，从联盟官方活动页获取（或从大淘客官方活动推广接口获取（饿了么微信推广活动ID：20150318020002192，饿了么外卖活动ID：20150318019998877，饿了么商超活动ID：1585018034441）
@pid string 非必须 推广pid，默认为在”我的应用“添加的pid
@relationId string 非必须 渠道id将会和传入的pid进行验证，验证通过将正常转链，请确认填入的渠道id是正确的
@unionId string 非必须 自定义输入串，英文和数字组成，长度不能大于12个字符，区分不同的推广渠道
"""
from dtkApi.apiRequest import Request


class ActivityLinkReq(Request):
    url='tb-service/activity-link'
    check_params=['promotionSceneId']
    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,promotionSceneId, pid=None, relationId=None, unionId=None):
        self.addParams('promotionSceneId', promotionSceneId)
        self.addParams('pid', pid)
        self.addParams('relationId', relationId)
        self.addParams('unionId', unionId)