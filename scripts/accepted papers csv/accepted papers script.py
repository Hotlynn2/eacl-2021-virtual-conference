#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np


# In[2]:


all_papers = pd.read_csv('all_papers.csv')
all_papers['title'] = all_papers['title'].astype(str)
accepted_papers = pd.read_excel('accepted.xlsx',  header=None)


# In[3]:


accepted_papers.columns = ['paper_id', 'oral_pos', 'paper_type', 'track', 'title', 'abstract', 'authors' ]


# In[4]:


accepted_papers['paper_id'] = accepted_papers['paper_id'].astype(str)


# In[5]:


all_papers['paper_id'] = all_papers.pdf_url.str.split('.').str[-1]


# In[8]:


accepted_papers['pdf_url'] = 'https://www.aclweb.org/anthology/2021.eacl-main.' + accepted_papers.paper_id


# In[9]:


accepted_papers = accepted_papers.drop(['paper_id', 'oral_pos'], axis = 1)


# In[10]:


accepted_papers


# In[ ]:




