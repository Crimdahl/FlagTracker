# -*- coding: utf-8 -*-

# Importing Required Libraries
import sys
sys.platform = "win32"
import codecs, json, os, re, io, threading, datetime, clr, math, subprocess, inspect
clr.AddReference("IronPython.Modules.dll")
clr.AddReferenceToFileAndPath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "References", "TwitchLib.PubSub.dll"))
from TwitchLib.PubSub import TwitchPubSub

#   Script Information <Required>
ScriptName = "FlagTracker"
Website = "https://www.twitch.tv/Crimdahl"
Description = "Tracks User Flag Redemptions by writing to json file."
Creator = "Crimdahl"
Version = "1.1.0"

#   Define Global Variables <Required>
ScriptPath = os.path.dirname(__file__)
GoogleUpdaterPath = os.path.join(ScriptPath, "GoogleSheetsUpdater.exe")
SettingsPath = os.path.join(ScriptPath, "settings.json")
ReadmePath = os.path.join(ScriptPath, "Readme.md")
ScriptSettings = None

RedemptionNames = []
Redemptions = []
RedemptionsPath = os.path.join(ScriptPath, "redemptions.json")

EventReceiver = None
ThreadQueue = []
Thread = None
PlayNextAt = datetime.datetime.now()

# Define Redemptions
class Redemption(object):
    def __init__(self, **kwargs):
        self.Username = kwargs["Username"] if "Username" in kwargs else "Unknown"
        self.Game = kwargs["Game"] if "Game" in kwargs else "Unknown"
        self.Message = kwargs["Message"] if "Message" in kwargs else "Unknown"

    def toJSON(self):
        return {"Username": self.Username, "Game": self.Game, "Message": self.Message}

    def setGame(self, value):
        self.Game = value

    def setUsername(self, value):
        self.Username = value

    def setMessage(self, value):
        self.Message = value
    
    

# Define Settings. If there is no settings file created, then use default values in else statement.
class Settings(object):
    def __init__(self, SettingsPath=None):
        if SettingsPath and os.path.isfile(SettingsPath):
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        else:
            #Output Settings
            self.EnableDebug = True
            self.EnableResponses = True
            self.DisplayMessageOnGameUnknown = False
            self.RunCommandsOnlyWhenLive = True
            self.DisplayPermissions = "Everyone"
            self.ModifyPermissions = "Moderator"
            self.CommandName = "queue"
            self.DisplayLimit = "10"

            #Twitch Settings
            self.TwitchOAuthToken = ""
            self.TwitchRewardNames = ""

            #Google Sheets Settings
            self.EnableGoogleSheets = False
            self.SpreadsheetID = ""
            self.Sheet = ""

            RedemptionNames = [name.strip() for name in self.TwitchRewardNames.split(",")]

    def Reload(self, jsondata):
        self.__dict__ = json.loads(jsondata, encoding="utf-8")
        RedemptionNames = [name.strip() for name in self["TwitchRewardNames"].split(",")]
        return

    def Save(self, SettingsPath):
        try:
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8")
        except:
            Log("Failed to save settings to the file. Fix error and try again")
        return

#   Process messages <Required>
def Execute(data):
    #Log(str(inspect.getmembers(data)))
    user_id = GetUserID(data.RawData)
    if (
        data.Message == "!" + ScriptSettings.CommandName
        and (Parent.HasPermission(data.User, ScriptSettings.DisplayPermissions, "") 
        or user_id == "216768170")
        and (not ScriptSettings.RunCommandsOnlyWhenLive 
            or (ScriptSettings.RunCommandsOnlyWhenLive and Parent.IsLive()))
        ):
        if ScriptSettings.EnableGoogleSheets and ScriptSettings.SpreadsheetID != "":
            Post("https://docs.google.com/spreadsheets/d/" + ScriptSettings.SpreadsheetID)
        else:
            if len(Redemptions) > 0:
                index = 1
                for redemption in Redemptions:
                    Log(redemption.Game)
                    if ScriptSettings.DisplayMessageOnGameUnknown and redemption.Game == "Unknown":
                        Post(str(index) + ") " + redemption.Username + " - " + redemption.Message)
                    else:
                        Post(str(index) + ") " + redemption.Username + " - " + redemption.Game)
                    index = index + 1
                    if index > ScriptSettings.DisplayLimit:
                        break
                return
            else:
                Post("The community queue is empty!")
    elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " remove") 
        and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
        or user_id == "216768170")
        and (not ScriptSettings.RunCommandsOnlyWhenLive 
            or (ScriptSettings.RunCommandsOnlyWhenLive and Parent.IsLive()))
        ):
        if data.GetParamCount() >= 3: 
            DataString = str(data.Message)
            DataArray = DataString[DataString.index("remove") + len("remove"):].replace(" ","").split(",")
            DataArray.sort()
            if ScriptSettings.EnableDebug: Log("Removing the following indexes from Redemptions: " + str(DataArray))
            RemovedCount = 1
            for num in DataArray:
                try:
                    Redemptions.pop(int(num) - RemovedCount)
                    RemovedCount = RemovedCount + 1
                except (ValueError, IndexError) as e:
                    if ScriptSettings.EnableDebug: Log("Error handled by remove: " + e.message)
                    continue
            SaveRedemptions()
        else:
            if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " remove <Comma-Separated Integer Indexes>")
    elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " add") 
        and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
        or user_id == "216768170")
        and (not ScriptSettings.RunCommandsOnlyWhenLive 
            or (ScriptSettings.RunCommandsOnlyWhenLive and Parent.IsLive()))
        ):
        if data.GetParamCount() >= 3: 
            DataString = str(data.Message)
            DataArray = DataString[DataString.index("add") + len("add"):].split("|")
            for info in DataArray:
                if ScriptSettings.EnableDebug: Log("Adding new redemption via add command: " + str(info))
                try:
                    NewUser = GetAttribute("Username", info)
                    NewMessage = GetAttribute("Message", info)
                    try:
                        NewGame = GetAttribute("Game", info)
                    except AttributeError:
                        NewGame = "Unknown"
                    Redemptions.append(Redemption(Username=NewUser, Message=NewMessage, Game=NewGame))
                except (ValueError, IndexError) as e:
                    if ScriptSettings.EnableDebug: Log("Error handled by add: " + e.message)
                    continue
            SaveRedemptions()
        else:
            if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " add Username:<UserName>, Message:<Message>, (Game:<Game>) | Username:<UserName>, ...")
    elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " edit") 
        and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
        or user_id == "216768170")
        and (not ScriptSettings.RunCommandsOnlyWhenLive 
            or (ScriptSettings.RunCommandsOnlyWhenLive and Parent.IsLive()))
        ):
        if data.GetParamCount() >= 3: 
            try:
                index = int(data.GetParam(2))
                data = str(data.Message)[len("!" + ScriptSettings.CommandName + " edit " + str(index)):]
                if "game" in data.lower():
                     Redemptions[index - 1].setGame(GetAttribute("Game", data)) 
                     SaveRedemptions()
                elif "message" in data.lower():
                     Redemptions[index - 1].setMessage(GetAttribute("Message", data)) 
                     SaveRedemptions()
                elif "username" in data.lower():
                     Redemptions[index - 1].setUsername(GetAttribute("Username", data)) 
                     SaveRedemptions()
                else:
                    if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " edit <Index> <Username/Game/Message>:<Value>")
                    if ScriptSettings.EnableDebug: Log("Edit function supplied incorrect argument: " + data)
            except ValueError as e:
                if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " edit <Index> <Username/Game/Message>:<Value>")
                if ScriptSettings.EnableDebug: Log("Error handled by edit: " + e.message)
        else:
            if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " edit <Index> <Username/Game/Message>:<Value>")
    
        
        

#   [Required] Tick method (Gets called during every iteration even when there is no incoming data)
def Tick():
    global PlayNextAt
    if PlayNextAt > datetime.datetime.now():
        return

    global Thread
    if Thread and Thread.isAlive() == False:
        Thread = None

    if Thread == None and len(ThreadQueue) > 0:
        if ScriptSettings.EnableDebug: Log("Starting new thread. " + str(PlayNextAt))
        Thread = ThreadQueue.pop(0)
        Thread.start()

    return
    
#   Reload settings and receiver when clicking Save Settings in the Chatbot
def ReloadSettings(jsonData):
    if ScriptSettings.EnableDebug: Log("Saving settings.")
    global EventReceiver
    try:
        #Reload settings
        ScriptSettings.__dict__ = json.loads(jsonData)
        ScriptSettings.Save(SettingsPath)

        Unload()
        Start()
        if ScriptSettings.EnableDebug: Log("Settings saved successfully")
    except Exception as e:
        if ScriptSettings.EnableDebug: Log(str(e))

    return

#   Init called on script load. <Required>
def Init():
    #Initialize Settings
    global ScriptSettings
    ScriptSettings = Settings(SettingsPath)
    ScriptSettings.Save(SettingsPath)

    #Initialize Redemption Receiver
    Start()
    LoadRedemptions()
    return

def Start():
    if ScriptSettings.EnableDebug: Log("Starting receiver")

    global EventReceiver
    EventReceiver = TwitchPubSub()
    EventReceiver.OnPubSubServiceConnected += EventReceiverConnected
    EventReceiver.OnRewardRedeemed += EventReceiverRewardRedeemed

    EventReceiver.Connect()
    return

def EventReceiverConnected(sender, e):
    if ScriptSettings.EnableDebug: Log("Event receiver connecting")
    #  Get Channel ID for Username
    headers = {
        "Client-ID": "7a4xexuuxvxw5jmb9httrqq9926frq",
        "Authorization": "Bearer " + ScriptSettings.TwitchOAuthToken
    }
    result = json.loads(Parent.GetRequest("https://api.twitch.tv/helix/users?login=" + Parent.GetChannelName(), headers))
    if ScriptSettings.EnableDebug: Log("result: " + str(result))
    user = json.loads(result["response"])
    id = user["data"][0]["id"]

    if ScriptSettings.EnableDebug: Log("Event receiver connected, sending topics for channel id: " + id)

    EventReceiver.ListenToRewards(id)
    EventReceiver.SendTopics(ScriptSettings.TwitchOAuthToken)
    return

def EventReceiverRewardRedeemed(sender, e):
    if ScriptSettings.EnableDebug: Log("Event triggered")

    dataUser = e.Login
    dataUserName = e.DisplayName
    reward = e.RewardTitle
    message = e.Message

    

    if e.RewardTitle in RedemptionNames:
        ThreadQueue.append(threading.Thread(target=RewardRedeemedWorker,args=(reward, message, dataUser, dataUserName)))
    return

def RewardRedeemedWorker(reward, message, dataUser, dataUserName):
    if ScriptSettings.EnableDebug:
        Log(dataUserName + " is redeeming " + reward + " with flag information " + message)

    MessageString = str(message)
    if any (keyword in MessageString for keyword in ["FF4FE", "Free Enterprise", "FFIV", "FF4", "whichburn", "kmain/summon/moon/trap", "spoon", "win:crystal"]):
        New_Game = "FF4 Free Enterprise"
    elif any (keyword in MessageString for keyword in ["WC", "Worlds Collide", "FFVIWC", "FF6WC"]) or len(MessageString) > 350:
        New_Game = "FF6 Worlds Collide"
    elif any (keyword in MessageString for keyword in ["BC", "Beyond Chaos", "FFVIBC", "FF6BC", "johnnydmad", "capslockoff", "alasdraco", "makeover" "notawaiter"]):
        New_Game = "FF6 Beyond Chaos"
    elif any (keyword in MessageString for keyword in ["TS", "Timespinner", "Lockbox", "Heirloom", "Fragile", "Talaria"]):
        New_Game = "Timespinner"
    elif any (keyword in MessageString for keyword in ["FFV", "Career", "FFVCD"]):
        New_Game = "FF5 Career Day"
    elif any (keyword in MessageString for keyword in ["SMRPG", "Super Mario RPG", "Geno", "Cspjl", "-fakeout"]):
        New_Game = "SMRPG Randomizer"
    elif any (keyword in MessageString for keyword in ["Secret of Mana", "SoM"]):
        New_Game = "Secret of Mana Randomizer"
    elif any (keyword in MessageString for keyword in ["Super Mario 3", "Mario 3", "SM3", "SM3R"]):
        New_Game = "Super Mario 3 Randomizer"
    else:
        New_Game = "Unknown"

    new_redemption = Redemption(Username=dataUserName, Game=New_Game, Message=message)
    Redemptions.append(new_redemption)
    SaveRedemptions()
    
    global PlayNextAt
    PlayNextAt = datetime.datetime.now() + datetime.timedelta(0, 0)
    return

def Unload():
    # Disconnect EventReceiver cleanly
    try:
        global EventReceiver
        if EventReceiver:
            EventReceiver.Disconnect()
            EventReceiver = None
    except:
        if ScriptSettings.EnableDebug: Log("Event receiver already disconnected")

    return

#   Opens readme file <Optional - DO NOT RENAME>
def openreadme():
    os.startfile(ReadmePath)
    return

#   Opens Twitch.TV website to ask permissions
def GetToken(): 
    os.startfile("https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=7a4xexuuxvxw5jmb9httrqq9926frq&redirect_uri=https://twitchapps.com/tokengen/&scope=channel:read:redemptions&force_verify=true")
    return

#   Helper method to log
def Log(message): 
    Parent.Log(ScriptName, message)

#   Helper method to post to Twitch Chat
def Post(message):
    Parent.SendStreamMessage(message)

def SaveRedemptions():
    try:        
        #if the redemptions file does not exist, create it
        if not os.path.exists(RedemptionsPath):
            with io.open(RedemptionsPath, 'w') as outfile:
                outfile.write(json.dumps({}))

        #record the questions
        with open (RedemptionsPath, 'w') as outfile:
            outfile.seek(0)
            #When writing the Questions to disk, use the Question.toJSON() function
            json.dump(Redemptions, outfile, indent=4, default=lambda q: q.toJSON())
            outfile.truncate()

        if ScriptSettings.EnableGoogleSheets: 
            if ScriptSettings.SpreadsheetID == "" or ScriptSettings.Sheet == "":
                Log("Error: You must enter a valid Spreadsheet ID and Sheet Name to use Google Sheets.")
                return
        os.system(GoogleUpdaterPath)
    except OSError as e:
        Log("ERROR: Unable to save redemptions! " + e.message)

def LoadRedemptions():
    #Ensure the questions file exists
    if os.path.exists(RedemptionsPath):
        try:
            with open(RedemptionsPath, "r") as infile:
                # filedata = io.open(RedemptionsPath)  #Read the file data
                objectdata = json.load(infile)    #Load the json data

                #For each object/question in the objectdata, create new questions and feed them to the questions_list
                for redemption in objectdata:
                    Redemptions.append(Redemption(Username=redemption["Username"], Game=redemption["Game"], Message=redemption["Message"]))
                if ScriptSettings.EnableDebug: Log("Redemptions loaded: " + str(len(Redemptions)))
        except ValueError:
            if ScriptSettings.EnableDebug: Log("Redemptions file exists, but contains no data.")

    else:
        if ScriptSettings.EnableDebug: Log("WARNING: No redemptions file exists. Creating one.")
        open(RedemptionsPath, "w").close

def GetAttribute(attribute, message):
    # if str(message).index(str(attribute)) > -1:
        attribute = attribute.lower() + ":"
        #The start index of the attribute begins at the end of the attribute designator, such as "game:"
        try:
            index_of_beginning_of_attribute = message.lower().index(attribute) + len(attribute)
        except ValueError as e:
            raise e
        #The end index of the attribute is at the last space before the next attribute designator, or at the end of the message
        try:
            index_of_end_of_attribute = message[index_of_beginning_of_attribute:index_of_beginning_of_attribute + message[index_of_beginning_of_attribute:].index(":")].rindex(",")
        except ValueError:
            #If this error is thrown, the end of the message was hit, so just return all of the remaining message
            return message[index_of_beginning_of_attribute:].strip()
        return message[index_of_beginning_of_attribute:index_of_beginning_of_attribute + index_of_end_of_attribute].strip().strip(",")
    # else:
    #     raise AttributeError(str(attribute) + " was not found in the supplied information.")

def GetUserID(rawdata):
    try:
        rawdata = rawdata[rawdata.index("user-id=") + len("user-id="):]
        rawdata = rawdata[:rawdata.index(";")]
    except Exception:
        return ""
    return rawdata

def testing():
    pass