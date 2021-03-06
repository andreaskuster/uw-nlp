from truecase_model import TrueCaser
from singlechar_dataset import TrueCaseDataset, TrueCaseDatasetImproved

import matplotlib.pyplot as plt

import pickle as pkl
import numpy as np
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix

import torch
from torch import nn
from torch.utils.data import DataLoader
from torch import optim

from tqdm import trange, tqdm

import os

TRAIN_PATH = '../datasets/wiki/input.txt'
VAL_PATH = '../datasets/wiki/val_input.txt'
TEST_PATH = '../datasets/wiki/test.txt'
MODEL_SAVE_PATH = 'models/'

HIDDEN_SIZE = 300

EPOCHS = 30
BATCH_SIZE = 100
OOV_RATE = 0.005

# AUTO FLAGS
_DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print('DEVICE USED: {}'.format(_DEVICE))


def train(model, optimizer, criterion, train_loader, val_loader):
    train_losses = []
    val_losses = []

    for epoch_idx in range(1, EPOCHS + 1):
        # Epoch
        optimizer.zero_grad()

        loss_epoch = 0.
        for inputs, labels in tqdm(train_loader, desc=f'Epoch {epoch_idx}', leave=False):
            optimizer.zero_grad()

            inputs, labels = inputs.to(_DEVICE), labels.to(_DEVICE)
            labels_predict, _ = model(inputs)

            # Reshape truth and predictions to match input to typical criterions
            labels_predict = labels_predict.reshape((-1, labels_predict.shape[-1]))
            labels = labels.reshape(-1)

            loss_curr = criterion(labels_predict, labels)

            loss_curr.backward()
            optimizer.step()

            loss_epoch += loss_curr.cpu().item()

        val_loss = 0.
        with torch.no_grad():
            for inputs, labels, masks in tqdm(val_loader, desc=f'Validation Epoch {epoch_idx}', leave=False):
                inputs, labels = inputs.to(_DEVICE), labels.to(_DEVICE)
                masks = masks.to(_DEVICE)
                labels_predict, _ = model(inputs)

                # Reshape truth and predictions to match input to typical criterions
                labels_predict = labels_predict.reshape((-1, labels_predict.shape[-1]))
                masks = masks.reshape(-1)
                labels = labels.reshape(-1)

                # Also apply mask to them though
                labels_predict = labels_predict[masks]
                labels = labels[masks]

                loss_curr = criterion(labels_predict, labels)

                val_loss += loss_curr.cpu().item()

        # Normalize losses
        val_loss /= len(val_loader)
        loss_epoch /= len(train_loader)

        print('Epoch: {}'.format(epoch_idx))
        print('\tLoss: {:.4f}'.format(loss_epoch))
        print('\tValidation Loss: {:.4f}'.format(val_loss))

        # Save model for each epoch
        torch.save(model.state_dict(), f'{MODEL_SAVE_PATH}/model_epoch_{epoch_idx}.pth')

        # Update loss tracking arrays
        val_losses.append(val_loss)
        train_losses.append(loss_curr)

    # Save loss arrays
    np.save(f'{MODEL_SAVE_PATH}/val_losses.npy', val_losses)
    np.save(f'{MODEL_SAVE_PATH}/train_losses.npy', train_losses)

    return model


def evaluate(model, criterion, data_loader):
    loss = 0.
    y_pred = []
    y_truth = []
    with torch.no_grad():
        for inputs, labels, masks in tqdm(data_loader, desc='Evaluating', leave=False):
            inputs, labels = inputs.to(_DEVICE), labels.to(_DEVICE)
            masks = masks.to(_DEVICE)
            labels_predict, _ = model(inputs)

            # Reshape truth and predictions to match input to typical criterions
            labels_predict = labels_predict.reshape((-1, labels_predict.shape[-1]))
            masks = masks.reshape(-1)
            labels = labels.reshape(-1)

            # Also apply mask to them though
            labels_predict = labels_predict[masks]
            labels = labels[masks]

            loss_curr = criterion(labels_predict, labels)

            labels_predict = torch.argmax(labels_predict, dim=1).cpu()
            y_pred.extend(labels_predict.tolist())
            y_truth.extend(labels.cpu().tolist())

            loss += loss_curr.cpu().item()

    return loss / len(data_loader), np.array(y_pred), np.array(y_truth)


def plot_confusion_matrix(cm, title='Confusion matrix', cmap=plt.cm.Blues):
    cm_normalized = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    plt.imshow(cm_normalized, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, ['Predicted True', 'Predicted False'], rotation=45)
    plt.yticks(tick_marks, ['Ground True', 'Ground False'])
    plt.tight_layout
    plt.ylabel('True label')
    plt.xlabel('Predicted label')


def main(train_path, val_path, test_path):
    dataset_type = TrueCaseDatasetImproved
    # Load data
    train_dataset = dataset_type(
        train_path,
        train=True,
        OOV_rate=OOV_RATE
    )
    val_dataset = dataset_type(
        val_path,
        token_dict=train_dataset.token_to_idx,
        train=False
    )
    test_dataset = dataset_type(
        test_path,
        token_dict=train_dataset.token_to_idx,
        train=False
    )

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE)

    # Load model
    model = TrueCaser(train_dataset.num_tokens(), HIDDEN_SIZE).to(_DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters())

    # Create the model directory
    if not os.path.exists(MODEL_SAVE_PATH):
        os.makedirs(MODEL_SAVE_PATH)

    # Call train function
    # ! COMMENT OUT IF ALREADY TRAINED
    # model = train(model, optimizer, criterion, train_loader, val_loader)
    # with open('token_to_idx.pkl', mode='wb') as f:
    #     pkl.dump(train_dataset.token_to_idx, f)

    # Load model with lowest validation error
    val_losses = np.load(f'{MODEL_SAVE_PATH}/val_losses.npy')
    min_idx = np.argmin(val_losses)
    eval_model = TrueCaser(train_dataset.num_tokens(), HIDDEN_SIZE)
    eval_model.load_state_dict(torch.load(f'{MODEL_SAVE_PATH}/model_epoch_{min_idx}.pth'))
    eval_model.to(_DEVICE)

    # Print various statistics and scores of that model
    test_loss, test_pred, test_truth = evaluate(eval_model, criterion, test_loader)
    print('\n\n')
    print(f'Best Model on Validation was after epoch number {min_idx}')
    print(f'\tValidation Loss: {val_losses[min_idx]}')
    print(f'\tTest Loss: {test_loss}')
    print(f'\tTest F1 Score: {f1_score(test_truth, test_pred)}')
    print(f'\tTest Accuracy: {accuracy_score(test_truth, test_pred)}')

    # Show confusion matrix
    plot_confusion_matrix(confusion_matrix(test_truth, test_pred))
    plt.show()

if __name__ == "__main__":
    main(TRAIN_PATH, VAL_PATH, TEST_PATH)
