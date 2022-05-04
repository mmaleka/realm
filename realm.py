import requests
import pandas as pd
from pandas import json_normalize
import datetime
from datetime import datetime
from dateutil.parser import parse
import json
from abc import ABC, abstractmethod


class filterData(ABC):

    def __init__(self, msg, url_api, url_api_exclusion):
        self.url_api = url_api
        self.url_api_exclusion = url_api_exclusion
        self.msg = msg
        # today date in format : DD-MM
        self.today = datetime.now().strftime("%m-%d")
        # today date in format : YYY-DD-MM
        self.today_full = datetime.now().strftime("%Y-%m-%d")
        # current year in format : YY
        self.yearNow = datetime.now().strftime("%Y")
        # Exclusion list
        self.exclusion_list = []
        # current year is leap year or not
        self.is_now_leap_year = True


    def getAPIData(self):
        # Get all employee data from API
        r = requests.get(self.url_api)
        # if the responce is succsesful then create a pandas dataframe and place the data in the dataframe
        if r.status_code == 200:
            data = r.json()
            if len(data) > 0:
                df = json_normalize(data)
            else:
                # if there is no data then create an empty dataframe
                df = pd.DataFrame(columns = ['id', 'name', 'lastname', 'lastname', 'employmentStartDate', 'employmentEndDate', 'lastNotification', 'lastBirthdayNotified'])
            return df

    def getExclusionList(self):
        r = requests.get(self.url_api_exclusion)
        if r.status_code == 200:
            data = r.json()
            self.exclusion_list = data

    def updateAPIData(self, employee_id, employee_data):
        url_api = self.url_api+"/"+str(employee_id)
        r = requests.patch(url_api, data=employee_data) 
        print(r.status_code)
        # if patch request is succsessfull (200) then return true
        if r.status_code == 200:
            return True
        # otherwise return false and dont send an email
        else:
            return False


    # filter for employee that has left the company
    def notleftCompany(self, employee_item):
        if employee_item['employmentEndDate'] != None:
            if employee_item['employmentEndDate'] > self.today_full:
                # employee has left the company
                return False
            elif employee_item['employmentEndDate'] < self.today_full:
                # employee has not yet left the company
                return True
        else:
            return True


    # filter for employee that has started working for the company
    def startedWorking(self, employee_item):
        # first check if employment start date is not none
        if employee_item['employmentStartDate'] != None:
            # Now check if the employment start date is less than todays date
            if employee_item['employmentStartDate'] < self.today_full:
                # the employee has started started working for the company
                return True
        else:
            return False
    

    def checkLeapYear(self):
        year = int(self.yearNow)
        # Checking if the given year is leap year  
        if((year % 400 == 0) or  (year % 100 != 0) and  (year % 4 == 0)):   
            self.is_now_leap_year = True
        # Else it is not a leap year  
        else:  
            self.is_now_leap_year = False
    


class SendEmployeeMessage(ABC):

    def __init__(self, filterData):
        self.filterData = filterData
        

    def sendEmail(self, employee_dict):
        if len(employee_dict['name']) > 0:
            employeeToString = ', '.join([str(elem) for elem in employee_dict['name']])
            message = self.filterData.msg + " " + employeeToString
            # will send an email here
            print("message: ", message)
        else:
            print("No employees to send message today")

    
    def getMessageNames(self):
        df_employeeList = self.filterData.getAPIData()
        exclusion_list = self.filterData.exclusion_list
        today_date = self.filterData.today
        today_full = self.filterData.today_full
        yearNow = self.filterData.yearNow
        is_now_leap_year = self.filterData.is_now_leap_year
        
        employee_dict = {
            'id':[],
            'name': [],
        }
        # firstly check if the dataframe is not empty
        if df_employeeList.empty == False:
            # Next loop through all the birthday list
            for index,item in df_employeeList.iterrows():
                
                # check if the employee has left the company
                employee_notleft = self.filterData.notleftCompany(employee_item=item)
                # check when the employee started working
                employee_startworking = self.filterData.startedWorking(employee_item=item)
                # check if the employee is part of the excluded list
                event_excluded = self.notReceiveWishes(employee_item=item, exclusion_list=exclusion_list)
                # check if employee birthday is today and if in leapyear
                check_employee_event = self.checkEventDay(employee_item=item, today_date=today_date, is_now_leap_year=is_now_leap_year) 
                # # check last time the employee was sent a notification
                check_last_notified = self.checkLastNotification(employee_item=item, yearNow=yearNow)
                

                rules = [
                    employee_notleft == True,
                    employee_startworking == True,
                    event_excluded == True,
                    check_employee_event == True,
                    check_last_notified == True
                ]

                # print(rules)
                # check if all conditions are true
                # if all conditions are then append today_employee_dict to send email
                if all(rules):
                    # make a put request to the API to update the lastBirthdayNotified field 
                    # this will ensure we do not send the same email to the same user
                    patch_api_last_notified = self.patchAPILastNotified(employee_item=item, today_full=today_full)
                    if patch_api_last_notified == True:
                        employee_dict['id'].append(item['id'])
                        employee_dict['name'].append(item['name'])
                    

                
                @abstractmethod
                def notReceiveWishes(self, employee_item=item, today_date=today_date):
                    pass
                @abstractmethod
                def checkEventDay(self, employee_item=item, today_date=today_date, is_now_leap_year=is_now_leap_year):
                    pass
                @abstractmethod
                def checkLastNotification(self, employee_item=item, yearNow=yearNow):
                    pass
                @abstractmethod
                def patchAPILastNotified(self, employee_item=item, today_full=today_full):
                    pass

                
            return employee_dict




class BirthDayWishes(SendEmployeeMessage):
    # Check if an employees birthday is today
    def checkEventDay(self, employee_item, today_date, is_now_leap_year):

        bday = parse(employee_item['dateOfBirth']).strftime("%m-%d")  
        date_28 = datetime.strptime('02-28', '%m-%d').strftime('%m-%d')  
        date_01 = datetime.strptime('03-01', '%m-%d').strftime('%m-%d')

        if bday == today_date:
            # check if employee birthday is today, return true
            return True

        elif is_now_leap_year == True:
            # if current year is leap year and birthday date=29-02 then
            # move birthday date to 28-02 i.e return true
            if (bday > date_28) and (bday < date_01):
                return True
            else:
                return False
        else:
            return False

    # This function will check the last time the user was sent a birthday
    # notification. If the notification was sent this year, then do not 
    # send another notification
    def checkLastNotification(self, employee_item, yearNow):
        # check if the lastBirthdayNotified is yearNow
        # if not equal then send birthday wish
        # else do not sent birthday wish
        if str(employee_item['lastBirthdayNotified']) != 'nan':
            byear = parse(employee_item['lastBirthdayNotified']).strftime("%Y")  
            if byear == yearNow:
                # birthday wish already sent for this year
                return False
            else:
                return True
        else:
            return True

    # filter employees configured to not receive birthday wishes
    def notReceiveWishes(self, employee_item, exclusion_list):
        if employee_item['id'] not in exclusion_list:
            return True
        else:
            return False

    def patchAPILastNotified(self, employee_item, today_full):
        # If update was successfull then send employee email
        id = employee_item['id']
        data = today_full
        update_lasteventnotification = self.filterData.updateAPIData(employee_id=id, employee_data=data)
        return update_lasteventnotification

        
class WorkAnniversary(SendEmployeeMessage):
    # This function can be extended to cater for work anniversaries
    print("can use this function for work anniversaries")
    def notReceiveWishes(self, employee_item, exclusion_list):
        pass
    
    def checkLastNotification(self, employee_item, yearNow):
        pass

    def checkEventDay(self, employee_item, today_date, is_now_leap_year):
        pass

    def patchAPILastNotified(self, employee_item, today_full):
        pass
# more other functions can be added here to cater for other events





if __name__ == "__main__":
    print("starting script")
    url_api = 'https://interview-assessment-1.realmdigital.co.za/employees'
    url_api_exclusion = 'https://interview-assessment-1.realmdigital.co.za/do-not-send-birthday-wishes'
    msg = "Happy Birthday"
    employee = BirthDayWishes(filterData(msg, url_api, url_api_exclusion))
    employee_event_dict = employee.getMessageNames()
    employee.sendEmail(employee_dict=employee_event_dict)


