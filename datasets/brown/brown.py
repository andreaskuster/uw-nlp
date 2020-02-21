import nltk
from truecase import load_truecaser, load_truecase_dataset, evaluate
import pickle as pkl

import torch
from torch import nn
from torch.utils.data import DataLoader

class Brown:

    def __init__(self):
        # download dataset
        nltk.download("brown")

    def load_data(self, text_map_func=lambda x: x, tag_map_func=lambda x: x):
        # split text from pos tag
        text, tag = [], []
        for tagged_sentence in nltk.corpus.brown.tagged_sents():
            sentence, tags = zip(*tagged_sentence)
            text.append(list(map(text_map_func, sentence)))
            tag.append(list(map(tag_map_func, tags)))
        # return as tuple
        return text, tag

    def load_data_lowercase(self):
        return self.load_data(text_map_func=str.lower)

    def load_data_truecase(self):
        raise NotImplementedError()


if __name__ == "__main__":
    # instantiate class
    brown = Brown()
    # get brown data
    data = brown.load_data()
    # get brown data, lowercase
    data_lower = brown.load_data_lowercase()
    # get brown data, truecase
    data_truecase = brown.load_data_truecase()
