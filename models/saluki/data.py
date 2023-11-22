import pandas as pd
import torch
from torch.utils.data import DataLoader
import torchdata.datapipes as dp
import torch.nn.functional as F
from sklearn.model_selection import train_test_split
from collections import defaultdict
from torch.utils.data.distributed import DistributedSampler
from functools import partial

class DegradationLoader(dp.iter.IterDataPipe):

    def __init__(self,data):
        self.data = data

    def __iter__(self):
        for sample in self.data.to_dict(orient='records'):
            yield sample

def make_dataset_splits(data,random_seed=65):
    '''Split the dataset into train, val, and test sets'''
    train,test = train_test_split(data,test_size=0.1,random_state=random_seed)
    train,val = train_test_split(train,test_size=0.1,random_state=random_seed)
    return DegradationLoader(test),DegradationLoader(val),DegradationLoader(train)

def numericalize_and_batch(x,leading_special=True,pad_to_max_len=True,is_human=False):
    '''Transforms a string of nucleotides into a list of integers'''

    mapping = {'A' : 0, 'C' : 1, 'G' : 2, 'T' : 3, '<score>' :4,'<pad>' : 5}
    B = defaultdict(list) 
    
    for entry in x:
        seq = [mapping[x] for x in entry['seq']]
        B['len'].append(len(seq))
        #B['id'].append(entry['id'])
        splice_sites = entry['splice_sites']
        coding_starts = entry['codon_starts']
        start_pos = coding_starts.index(1.0)
        # fixed length like in paper 
        if pad_to_max_len:
            diff = 12288 - len(seq)
            if diff > 0:
                seq = seq + [mapping['<pad>']]*diff
                splice_sites = splice_sites + [0]*diff
                coding_starts = coding_starts + [0]*diff
        # onehot_encode sequence
        seq = torch.tensor(seq,dtype=torch.int64)
        seq = F.one_hot(seq,num_classes=6).float()
        # include two binary auxiliary tracks 
        splice_sites = torch.tensor(splice_sites,dtype=torch.float32).unsqueeze(1)
        coding_starts = torch.tensor(coding_starts,dtype=torch.float32).unsqueeze(1)
        seq = torch.cat([seq,splice_sites,coding_starts],dim=1)
        B['seq'].append(seq) 
        # add the target
        half_life = torch.tensor(entry['half_life'],dtype=torch.float32)
        B['half_life'].append(half_life) 

    seq = torch.nn.utils.rnn.pad_sequence(B['seq'],
                                          batch_first=True,
                                          padding_value=0)
    half_lives = torch.stack(B['half_life'],dim=0)
    return seq,B['len'],half_lives,is_human

def build_datapipe(fname,batch_size=None,max_tokens=60000,
                   pad_to_max_len=True,is_human=False):
    
    data = parse_json(fname) 
    dataset = DegradationLoader(data)
    dataset = dataset.shuffle()

    stack_fn = partial(numericalize_and_batch,
                       leading_special=True,
                       pad_to_max_len=pad_to_max_len,
                       is_human=is_human)

    # variable batch size by similar length 
    if batch_size is None:
        len_fn = lambda x: len(x['seq'])
        dataset = dataset.max_token_bucketize(max_token_count=max_tokens,
                                        buffer_size=1000,
                                        len_fn=len_fn,
                                        include_padding=True)
    # fixed batch_size 
    else: 
        dataset = dataset.batch(batch_size)

    dataset = dataset.map(stack_fn)
    dataset = dataset.shuffle()
    return dataset

def dataloader_from_json(data_dir,split,batch_size=None,max_tokens=60000):
    '''Use datapipes to make dataloaders and numericalize utr seq'''

    dataset1 = build_datapipe(f'{data_dir}/human/{split}.json',
                              batch_size=batch_size,
                              max_tokens=max_tokens,
                              is_human=True)
    dataset2 = build_datapipe(f'{data_dir}/mouse/{split}.json',
                              batch_size=batch_size,
                              max_tokens=max_tokens,
                              is_human=False)

    # alternate batches from human and mouse datasets
    dataset = dataset1.mux_longest(dataset2)
    dataloader = DataLoader(dataset,batch_size=None,shuffle=True)
    return dataloader

def parse_json(filename):
    return pd.read_json(filename,lines=True)