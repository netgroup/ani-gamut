#classe non pensata essere thread-safe!!
class dbTransaction:
    def __init__(self):
        self.__transactionElement={}
        self.__transactionID=0
        self.__messageID=0

    def newTransaction(self,src_host,dst_host,path,encap_info,decap_info):
        transactionID = self.__transactionID
        self.__transactionID += 1
        element = {
            "id":transactionID, #superfluo ma non se sa mai
            "src_host":src_host,
            "dst_host":dst_host,
            "encap":encap_info,
            "decap":decap_info,
            "path":path
            #"message_list":msg_ids
        }
        self.__transactionElement[transactionID] = element 
        return transactionID

    def get_messageID(self):
        messageID = self.__messageID
        self.__messageID = self.__messageID +1
        return messageID

    def get_transaction(self,id):
        e = self.__transactionElement.get(id,{})
        if not e:  
            return {"error":"transaction id not valid"}    
        return e 

    def print_db(self):
        for key in self.__transactionElement.keys():
            e = self.__transactionElement[key]
            print(e)
        