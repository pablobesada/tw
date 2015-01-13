#encoding: utf-8

from pipeline import Pipeline
from mongo import MongoManager
from datetime import datetime, timedelta
from pprint import pprint
from tweet import Tweet
from classifiermanager import ClassifierManager
from brandclassifier import ProductMatch

class TweetSaveForPolls(Pipeline.Stage):  #aca se graba en las base de datos de polls

    def processItem(self, item):
        polls_ht = MongoManager.getPollsByHashtag(max_age=timedelta(seconds=10))
        tweet = Tweet.createFromRawGnipActivity(item)
        pprint(tweet)
        for ht in tweet.getHashtags():
            if ht in polls_ht:
                for poll in polls_ht[ht]:
                    MongoManager.saveDocument("polls_" + poll.getId(), tweet.getDictionary())
                    pprint("grabando tweet para poll %s" % poll.getName())
        return tweet

class TweetProcessCampaign(Pipeline.Stage):  
    #aca se crea como tweet y se aplica brand classifier / recibe un dict y devuelve un tweet

    
    def processItem(self, tweet):
        accs = MongoManager.getActiveAccounts(max_age=timedelta(seconds=10))
        #pprint (tweet)
        #pprint (tweet.getExtractedInfo())
        follow_accounts= MongoManager.getFollowAccountsbyCampaign(max_age=timedelta(seconds=10))
        bcs = ClassifierManager.getBrandClassifiers() #esto tendria que esta cacheado tambien en classifiermanager
        tcs = None
        pms = self.getBrandClassifiersByCampaign(tweet, bcs, follow_accounts) ##FALTA AGREGAR TAMBIEN A LOS TWEETS QUE NO MATCHEAN PERO QUE SON DE UN USUARIO SEGUIDO POR LA MARCA
        
        for cid, pmlist in pms.items():
            if tcs is None: tcs = ClassifierManager.getTopicClassifiers()
            tms = self.getTopicClassifiers(tweet, cid, tcs)
            tweet.setExtractedTopics(tms)
            tweet.setExtractedInfo(pmlist)
            tweet.resetFollowAccountsMentionCount()
            user_mentions = tweet.getUserMentions()
            for fa in follow_accounts:
                if fa in user_mentions:
                    for fainfo in follow_accounts[fa]:
                        if fainfo['cid'] == cid:
                            tweet.setFollowAccountsMentionCount(fa, 1)
            MongoManager.saveDocument("tweets_%s" % cid, tweet.getDictionary())
            
        return None #no devuelvo nada para que no se acumulen los tweets en la ultima lista y se sature la memoria            


    def getBrandClassifiersByCampaign(self, tweet, bcs, follow_accounts):
        pms = {}
        for bc in bcs:
            if not bc.campaign_id in pms: pms[bc.campaign_id] = []
            pms[bc.campaign_id].extend([pm.getDictionary() for pm in bc.extract(tweet.getText())])
        if tweet.getUsername() in follow_accounts:
            for fainfo in follow_accounts[tweet.getUsername()]:
                pm = ProductMatch()
                pm.brand = fainfo['brand']
                pm.campaign_id = fainfo['cid']
                pm.confidence = 5
                pms[pm.campaign_id].append(pm.getDictionary())
        for cid, pmlist in pms.items():
            pms[cid].sort(key=lambda x: x['confidence'], reverse=True)
            if not pms[cid] or pms[cid][0]['confidence'] < 0:
                del pms[cid]
        return pms

                            
    def getTopicClassifiers(self, tweet, campaign_id, tcs):                            
        #solo aplico topics para las campañas que hayan matcheado el tweet y tengan x_extracted_info
        tms = []
        for topic_id, topic_classiffier in tcs.get(campaign_id, {}).items():
            tm = topic_classiffier.extract(tweet.getText())
            if tm: tms.append(tm.getDictionary())
        if tms: tms.sort(key=lambda x: x['confidence'], reverse=True)
        return tms

    




def getPipelineStageClasses():
    return [TweetSaveForPolls, TweetProcessCampaign]
    #return [TweetProcessStage_1, TweetProcessStage_2, TweetSaveStage]