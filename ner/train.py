# coding=utf-8
from __future__ import print_function
import optparse
import itertools
from collections import OrderedDict
import loader
import torch
import time
import _pickle as cPickle
from torch.autograd import Variable
import matplotlib.pyplot as plt
import sys
# import visdom
from utils import *
from loader import *
from model import BiLSTM_CRF
t = time.time()
models_path = "models/"

optparser = optparse.OptionParser()
optparser.add_option(
    "-T", "--train", default="dataset/eng.train",
    help="Train set location"
)
optparser.add_option(
    "-d", "--dev", default="dataset/eng.testa",
    help="Dev set location"
)
optparser.add_option(
    "-t", "--test", default="dataset/eng.testb",
    help="Test set location"
)

optparser.add_option(
    "-s", "--tag_scheme", default="iobes",
    help="Tagging scheme (IOB or IOBES)"
)
optparser.add_option(
    "-l", "--case", default="0",
    type='int', help="Lowercase words (this will not affect character inputs)"
)
optparser.add_option(
    "-c", "--train_mode", default="cased",
     help="cased, uncased, augmented, mixed and truecased"
)
optparser.add_option(
    "-y", "--dev_mode", default="cased",
     help="cased, uncased, augmented, mixed and truecased"
)
optparser.add_option(
    "-z", "--zeros", default="0",
    type='int', help="Replace digits with 0"
)
optparser.add_option(
    "-C", "--char_lstm_dim", default="40",
    type='int', help="Char LSTM hidden layer size"
)
optparser.add_option(
    "-b", "--char_bidirect", default="1",
    type='int', help="Use a bidirectional LSTM for chars"
)
optparser.add_option(
    "-w", "--word_dim", default="300",
    type='int', help="Token embedding dimension"
)
optparser.add_option(
    "-W", "--word_lstm_dim", default="400",
    type='int', help="Token LSTM hidden layer size"
)
optparser.add_option(
    "-B", "--word_bidirect", default="1",
    type='int', help="Use a bidirectional LSTM for words"
)
optparser.add_option(
    "-p", "--pre_emb", default="models/glove.840B.300d.txt",
    help="Location of pretrained embeddings"
)
optparser.add_option(
    "-A", "--all_emb", default="1",
    type='int', help="Load all embeddings"
)
optparser.add_option(
    "-a", "--cap_dim", default="0",
    type='int', help="Capitalization feature dimension (0 to disable)"
)
optparser.add_option(
    "-f", "--crf", default="1",
    type='int', help="Use CRF (0 to disable)"
)
optparser.add_option(
    "-D", "--dropout", default="0.5",
    type='float', help="Droupout on the input (0 = no dropout)"
)
optparser.add_option(
    "-r", "--reload", default="0",
    type='int', help="Reload the last saved model"
)
optparser.add_option(
    "-g", '--use_gpu', default='1',
    type='int', help='whether or not to ues gpu'
)
optparser.add_option(
    '--name', default='mixed_test',
    help='model name'
)
opts = optparser.parse_args()[0]

parameters = OrderedDict()
parameters['tag_scheme'] = opts.tag_scheme
parameters['zeros'] = opts.zeros == 1
parameters['char_lstm_dim'] = opts.char_lstm_dim
parameters['char_bidirect'] = opts.char_bidirect == 1
parameters['word_dim'] = opts.word_dim
parameters['word_lstm_dim'] = opts.word_lstm_dim
parameters['word_bidirect'] = opts.word_bidirect == 1
parameters['pre_emb'] = opts.pre_emb
parameters['all_emb'] = opts.all_emb == 1
parameters['cap_dim'] = opts.cap_dim
parameters['crf'] = opts.crf == 1
parameters['dropout'] = opts.dropout
parameters['reload'] = opts.reload == 1
parameters['name'] = opts.name
parameters['case'] = opts.case
case= opts.case
parameters['use_gpu'] = opts.use_gpu == 1 and torch.cuda.is_available()
use_gpu = parameters['use_gpu']

mapping_file = 'models/mixed_mapping.pkl'

name = parameters['name']
model_name = models_path + name #get_name(parameters)
tmp_model = model_name + '.tmp'


assert os.path.isfile(opts.train)
assert os.path.isfile(opts.dev)
assert os.path.isfile(opts.test)
assert 0. <= parameters['dropout'] < 1.0
assert parameters['tag_scheme'] in ['iob', 'iobes']
assert not parameters['all_emb'] or parameters['pre_emb']
assert not parameters['pre_emb'] or parameters['word_dim'] > 0
assert not parameters['pre_emb'] or os.path.isfile(parameters['pre_emb'])

if not os.path.isfile(eval_script):
    raise Exception('CoNLL evaluation script not found at "%s"' % eval_script)
if not os.path.exists(eval_temp):
    os.makedirs(eval_temp)
if not os.path.exists(models_path):
    os.makedirs(models_path)

zeros = parameters['zeros']
tag_scheme = parameters['tag_scheme']

train_sentences = loader.load_sentences(opts.train, case, zeros)
dev_sentences = loader.load_sentences(opts.dev, case, zeros)
test_sentences = loader.load_sentences(opts.test, case, zeros)

update_tag_scheme(train_sentences, tag_scheme)
update_tag_scheme(dev_sentences, tag_scheme)
update_tag_scheme(test_sentences, tag_scheme)

dico_words_train = word_mapping(train_sentences, case)[0]

dico_words, word_to_id, id_to_word = augment_with_pretrained(
        dico_words_train.copy(),
        parameters['pre_emb'],
        list(itertools.chain.from_iterable(
            [[w[0] for w in s] for s in dev_sentences + test_sentences])
        ) if not parameters['all_emb'] else None
    )

dico_chars, char_to_id, id_to_char = char_mapping(train_sentences)
dico_tags, tag_to_id, id_to_tag = tag_mapping(train_sentences)


if opts.train_mode == "cased":   
    train_data = prepare_dataset(
        train_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "uncased":
    train_data = prepare_dataset(
        train_sentences, word_to_id, char_to_id, tag_to_id, True
    )
if opts.train_mode == "augmented":
    train_data = prepare_dataset_cased_uncased(
        train_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "mixed":
    train_data = prepare_dataset_mixed(
        train_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "truecase":
    train_data = prepare_dataset_truecased(
        train_sentences, word_to_id, char_to_id, tag_to_id, True
    )
if opts.train_mode == "cased":   
    dev_data = prepare_dataset(
        dev_sentences, word_to_id, char_to_id, tag_to_id, False
    )
    test_data = prepare_dataset(
        test_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "uncased":
    dev_data = prepare_dataset(
        dev_sentences, word_to_id, char_to_id, tag_to_id, True
    )
    test_data = prepare_dataset(
        test_sentences, word_to_id, char_to_id, tag_to_id, True
    )
if opts.train_mode == "augmented":
    dev_data = prepare_dataset_cased_uncased(
        dev_sentences, word_to_id, char_to_id, tag_to_id, False
    )
    test_data = prepare_dataset_cased_uncased(
        test_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "mixed":
    dev_data = prepare_dataset_mixed(
        dev_sentences, word_to_id, char_to_id, tag_to_id, False
    )
    test_data = prepare_dataset_mixed(
        test_sentences, word_to_id, char_to_id, tag_to_id, False
    )
if opts.train_mode == "truecase":
    dev_data = prepare_dataset_truecased(
        dev_sentences, word_to_id, char_to_id, tag_to_id, True
    )
    test_data = prepare_dataset_truecased(
        test_sentences, word_to_id, char_to_id, tag_to_id, True
    )



print("%i / %i / %i sentences in train / dev / test." % (
    len(train_data), len(dev_data), len(test_data)))

all_word_embeds = {}
for i, line in enumerate(codecs.open(opts.pre_emb, 'r', 'utf-8')):
    s = line.strip().split()
    if len(s) == parameters['word_dim'] + 1:
        all_word_embeds[s[0]] = np.array([float(i) for i in s[1:]])

word_embeds = np.random.uniform(-np.sqrt(0.06), np.sqrt(0.06), (len(word_to_id), opts.word_dim))

for w in word_to_id:
    if w in all_word_embeds:
        word_embeds[word_to_id[w]] = all_word_embeds[w]
    elif w.lower() in all_word_embeds:
        word_embeds[word_to_id[w]] = all_word_embeds[w.lower()]

print('Loaded %i pretrained embeddings.' % len(all_word_embeds))

with open(mapping_file, 'wb') as f:
    mappings = {
        'word_to_id': word_to_id,
        'tag_to_id': tag_to_id,
        'char_to_id': char_to_id,
        'parameters': parameters,
        'word_embeds': word_embeds
    }
    cPickle.dump(mappings, f)

print('word_to_id: ', len(word_to_id))
model = BiLSTM_CRF(vocab_size=len(word_to_id),
                   tag_to_ix=tag_to_id,
                   embedding_dim=parameters['word_dim'],
                   hidden_dim=parameters['word_lstm_dim'],
                   use_gpu=use_gpu,
                   char_to_ix=char_to_id,
                   pre_word_embeds=word_embeds,
                   use_crf=parameters['crf'])

if parameters['reload']:
    model.load_state_dict(torch.load(model_name))
if use_gpu:
    model.cuda()
learning_rate = 0.015
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate, momentum=0.9)
losses = []
loss = 0.0
best_dev_F = -1.0
best_test_F = -1.0
best_train_F = -1.0
all_F = [[0, 0, 0]]
plot_every = 1000
eval_every = 2000
count = 0
# vis = visdom.Visdom()
sys.stdout.flush()


def evaluating(model, datas, best_F):
    prediction = []
    save = False
    new_F = 0.0
    confusion_matrix = torch.zeros((len(tag_to_id) - 2, len(tag_to_id) - 2))
    for data in datas:
        ground_truth_id = data['tags']
        words = data['str_words']
        chars2 = data['chars']
        caps = data['caps']

        chars2_sorted = sorted(chars2, key=lambda p: len(p), reverse=True)
        d = {}
        for i, ci in enumerate(chars2):
            for j, cj in enumerate(chars2_sorted):
                if ci == cj and not j in d and not i in d.values():
                    d[j] = i
                    continue
        chars2_length = [len(c) for c in chars2_sorted]
        char_maxl = max(chars2_length)
        chars2_mask = np.zeros((len(chars2_sorted), char_maxl), dtype='int')
        for i, c in enumerate(chars2_sorted):
            chars2_mask[i, :chars2_length[i]] = c
        chars2_mask = Variable(torch.LongTensor(chars2_mask))
        dwords = Variable(torch.LongTensor(data['words']))
        dcaps = Variable(torch.LongTensor(caps))
        if use_gpu:
            val, out = model(dwords.cuda(), chars2_mask.cuda(), dcaps.cuda(), chars2_length, d)
        else:
            val, out = model(dwords, chars2_mask, dcaps, chars2_length, d)
        predicted_id = out
        for (word, true_id, pred_id) in zip(words, ground_truth_id, predicted_id):
            line = ' '.join([word, id_to_tag[true_id], id_to_tag[pred_id]])
            prediction.append(line)
            confusion_matrix[true_id, pred_id] += 1
        prediction.append('')
    predf = eval_temp + '/c_pred.' + name
    scoref = eval_temp + '/c_score.' + name

    with open(predf, 'w') as f:
        f.write('\n'.join(prediction))

    os.system('%s < %s > %s' % (eval_script, predf, scoref))

    eval_lines = [l.rstrip() for l in codecs.open(scoref, 'r', 'utf8')]

    for i, line in enumerate(eval_lines):
        print(line)
        if i == 1:
            new_F = float(line.strip().split()[-1])
            if new_F > best_F:
                best_F = new_F
                save = True
                print('the best F is ', new_F)

    print(("{: >2}{: >7}{: >7}%s{: >9}" % ("{: >7}" * confusion_matrix.size(0))).format(
        "ID", "NE", "Total",
        *([id_to_tag[i] for i in range(confusion_matrix.size(0))] + ["Percent"])
    ))
    for i in range(confusion_matrix.size(0)):
        print(("{: >2}{: >7}{: >7}%s{: >9}" % ("{: >7}" * confusion_matrix.size(0))).format(
            str(i), id_to_tag[i], str(confusion_matrix[i].sum()),
            *([confusion_matrix[i][j] for j in range(confusion_matrix.size(0))] +
              ["%.3f" % (confusion_matrix[i][i] * 100. / max(1, confusion_matrix[i].sum()))])
        ))
    return best_F, new_F, save

model.train(True)
for epoch in range(1, 150):
    for i, index in enumerate(np.random.permutation(len(train_data))):
        tr = time.time()
        count += 1
        data = train_data[index]
        model.zero_grad()

        sentence_in = data['words']
        sentence_in = Variable(torch.LongTensor(sentence_in))
        tags = data['tags']
        chars2 = data['chars']

        ######### char lstm
        chars2_sorted = sorted(chars2, key=lambda p: len(p), reverse=True)
        d = {}
        for i, ci in enumerate(chars2):
            for j, cj in enumerate(chars2_sorted):
                if ci == cj and not j in d and not i in d.values():
                    d[j] = i
                    continue
        chars2_length = [len(c) for c in chars2_sorted]
        char_maxl = max(chars2_length)
        chars2_mask = np.zeros((len(chars2_sorted), char_maxl), dtype='int')
        for i, c in enumerate(chars2_sorted):
            chars2_mask[i, :chars2_length[i]] = c
        chars2_mask = Variable(torch.LongTensor(chars2_mask))
        targets = torch.LongTensor(tags)
        caps = Variable(torch.LongTensor(data['caps']))
        if use_gpu:
            neg_log_likelihood = model.neg_log_likelihood(sentence_in.cuda(), targets.cuda(), chars2_mask.cuda(), caps.cuda(), chars2_length, d)
        else:
            neg_log_likelihood = model.neg_log_likelihood(sentence_in, targets, chars2_mask, caps, chars2_length, d)
        # print(neg_log_likelihood.item()) 
        loss += neg_log_likelihood.data / len(data['words'])
        neg_log_likelihood.backward()
        torch.nn.utils.clip_grad_norm(model.parameters(), 5.0)
        optimizer.step()

        if count % plot_every == 0:
            loss /= plot_every
            print(count, ': ', loss)
            if losses == []:
                losses.append(loss)
            losses.append(loss)
            text = '<p>' + '</p><p>'.join([str(l) for l in losses[-9:]]) + '</p>'
            losswin = 'loss_' + name
            textwin = 'loss_text_' + name
            loss = 0.0

        if count % (eval_every) == 0 and count > (eval_every * 20) or \
                count % (eval_every*4) == 0 and count < (eval_every * 20):
            model.train(False)
            # best_train_F, new_train_F, _ = evaluating(model, test_train_data, best_train_F)
            best_dev_F, new_dev_F, save = evaluating(model, dev_data, best_dev_F)
            if save:
                torch.save(model, model_name)
            best_test_F, new_test_F, _ = evaluating(model, test_data, best_test_F)
            sys.stdout.flush()

            all_F.append([ new_dev_F, new_test_F])
            Fwin = 'F-score of {train, dev, test}_' + name
            model.train(True)

        if count % len(train_data) == 0:
            adjust_learning_rate(optimizer, lr=learning_rate/(1+0.05*count/len(train_data)))


print(time.time() - t)

plt.plot(losses)
plt.show()
