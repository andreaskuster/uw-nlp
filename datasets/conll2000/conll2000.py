#!/usr/bin/env python3
# encoding: utf-8

"""
    Copyright (C) 2020  Andreas Kuster

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Andreas Kuster"
__copyright__ = "Copyright 2020"
__license__ = "GPL"

import nltk
import random

from typing import Tuple, List

from truecase.external_utils import predict_truecasing
from datasets import AbstractLoader


class CoNLL2000(AbstractLoader):

    def __init__(self):
        # initialize super class
        super().__init__()
        # download dataset
        nltk.download("conll2000")

    def load_data(self, text_map_func=lambda x: x, tag_map_func=lambda x: x) -> Tuple[List, List]:
        # split text from pos tag
        text, tag = list(), list()
        for tagged_sentence in nltk.corpus.conll2000.tagged_sents():
            sentence, tags = zip(*tagged_sentence)
            text.append(list(map(text_map_func, sentence)))
            tag.append(list(map(tag_map_func, tags)))
        # return as tuple
        return text, tag

    def load_data_lowercase(self) -> Tuple[List, List]:
        # apply lowercase function to the dataset
        return self.load_data(text_map_func=str.lower)

    def load_data_truecase(self) -> Tuple[List, List]:
        # fetch lowercase dataset and truecase it
        lower_sentence, tag = self.load_data_lowercase()
        return predict_truecasing(lower_sentence), tag

    def load_data_cased_and_uncased(self) -> Tuple[List, List]:
        # fetch cased and uncased dataset and concatenate them
        sentence_c, tag_c = self.load_data()
        sentence_u, tag_u = self.load_data_lowercase()
        return sentence_c + sentence_u, tag_c + tag_u

    def load_data_half_mixed(self) -> Tuple[List, List]:
        # fetch cased dataset
        sentence, tag = self.load_data()
        # generate 50% random indices from 0..len(sentence)-1
        rand_samples = random.sample(range(0, len(sentence)), int(0.5*len(sentence)))
        # lowercase the elements at the address of the indices
        for index in rand_samples:
            sentence[index] = list(map(str.lower, sentence[index]))
        return sentence, tag


if __name__ == "__main__":
    # instantiate class
    conll2000 = CoNLL2000()
    # get conll2000 data
    data = conll2000.load_data()
    # get conll2000 data, lowercase
    data_lower = conll2000.load_data_lowercase()
    # get truecase conll2000 data
    data_truecase = conll2000.load_data_truecase()
    # get c+u conll2000 data (full dataset cased and uncased)
    data_cu = conll2000.load_data_cased_and_uncased()
    # get hm conll2000 data (50% randomly lowercase)
    data_hm = conll2000.load_data_half_mixed()
