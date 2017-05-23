'''
Test cyclegan using MNIST
'''
import json
import os

import keras.backend as k
import numpy as np
from keras.datasets import cifar10, mnist
from keras.layers import Input
from keras.models import Model
from keras.optimizers import Adam
from PIL import Image

import context
from cyclegan.losses import *
from cyclegan.models import mnist_discriminator, mnist_generator


def load_mnist():
    '''
    returns mnist_data
    '''
    # input image dimensions
    img_rows, img_cols = 28, 28

    # the data, shuffled and split between train and test sets
    (x_train, y_train), (x_test, y_test) = mnist.load_data()

    if k.image_data_format() == 'channels_first':
        x_train = x_train.reshape(x_train.shape[0], 1, img_rows, img_cols)
        input_shape = (1, img_rows, img_cols)
    else:
        x_train = x_train.reshape(x_train.shape[0], img_rows, img_cols, 1)
        input_shape = (img_rows, img_cols, 1)

    x_train = x_train.astype(k.floatx())
    x_train /= 255
    return input_shape, x_train

def load_input_images(from_jpegs=False):
    current_dir = os.path.dirname(__file__)
    image_names = os.listdir(os.path.join(current_dir, 'images'))
    images = np.ndarray((len(image_names), 28, 28), dtype=np.uint8)
    for i, filename in enumerate(image_names):
        images[i] = Image.open(os.path.join(current_dir,
                                            'images',
                                            filename)).resize((28, 28)).convert('L')
    images = images.astype('float32')
    images /= 255
    if k.image_data_format() == 'channels_first':
        images = images.reshape(images.shape[0], 1, 28, 28)
    else:
        images = images.reshape(images.shape[0], 28, 28, 1)
    return images

# def load_cfar_data():
#     (x_train, y_train), (x_test, y_test) = cifar10.load_data()

#     # Get the cat images.
#     cats = np.where(y_train == 3)[0]
#     cat_images = x_train[cats]

#     # Convert to greyscale and resize.
#     mniny_cat_images =[np.array(Image.fromarray(image).convert('L').resize((28, 28)))
#                                  for image in cat_images]
#     mniny_cat_images = np.array(mniny_cat_images, dtype=k.floatx())

#     # Make the numbers smaller.
#     mniny_cat_images /= 255

#     # Reshape for theano.
#     if k.image_data_format() == 'channels_first':
#         images = mniny_cat_images.reshape(mniny_cat_images.shape[0], 1, 28, 28)
#     else:
#         images = mniny_cat_images.reshape(mniny_cat_images.shape[0], 28, 28, 1)
#     return images


def prettify(image):
    image *= 255
    image = np.uint8(image)
    if k.image_data_format() == 'channels_first':
        image = np.reshape(image, (image.shape[2], image.shape[3]))
    else:
        image = np.reshape(image, (image.shape[1], image.shape[2]))
    return image

def test_cyclegan():
    mnist_shape, mnist_images = load_mnist()
    cats = load_input_images()

    nb_epochs = 200
    batch_size = 128
    adam_lr = 0.0002
    adam_beta_1 = 0.5
    adam_decay = 0.000001
    history_size = int(batch_size * 7/3)
    generation_history_mnist = None
    generation_history_cats = None
    SAVEPATH = 'data'

    mnist_input = Input(mnist_shape)
    cat_input = Input(mnist_shape)

    generator_cats = mnist_generator(mnist_shape)
    discriminator_cats = mnist_discriminator(mnist_shape)
    generator_mnist = mnist_generator(mnist_shape)
    discriminator_mnist = mnist_discriminator(mnist_shape)

    discriminator_cats.compile(optimizer=Adam(lr=adam_lr, beta_1=adam_beta_1, decay=adam_decay), loss='mean_squared_error')
    discriminator_mnist.compile(optimizer=Adam(lr=adam_lr, beta_1=adam_beta_1, decay=adam_decay), loss='mean_squared_error')
    generator_cats.compile(optimizer=Adam(lr=adam_lr, beta_1=adam_beta_1, decay=adam_decay), loss='mean_squared_error')
    generator_mnist.compile(optimizer=Adam(lr=adam_lr, beta_1=adam_beta_1, decay=adam_decay), loss='mean_squared_error')

    fake_cat = generator_cats(mnist_input)
    fake_mnist = generator_mnist(cat_input)

    # Only train discriminator during first phase
    # (only affects new models when they are compiled)
    discriminator_cats.trainable = False
    discriminator_mnist.trainable = False

    gen_trainer = Model([cat_input, mnist_input], [discriminator_cats(fake_cat),  discriminator_mnist(fake_mnist),
                                               generator_mnist(fake_cat), generator_cats(fake_mnist)])

    gen_trainer.compile(optimizer=Adam(lr=adam_lr, beta_1=adam_beta_1, decay=adam_decay), 
                    loss=['mean_squared_error', 'mean_squared_error', cycle_loss, cycle_loss], 
                    loss_weights=[1., 1., 10., 10.])

    # training time

    mnist_discrim_loss = []
    cats_discrim_loss = []
    mnist_gen_loss = []
    cats_gen_loss = []
    mnist_cyc_loss = []
    cats_cyc_loss = []

    if not os.path.exists(SAVEPATH):
        os.makedirs(os.path.join(SAVEPATH, 'images'))

    for epoch in range(nb_epochs):
        print("\n\n================================================")
        print("Epoch", epoch, '\n')
        if epoch == 0: # Initialize history for training the discriminator
                mnist_indices = np.random.choice(mnist_images.shape[0], history_size)
                generation_history_mnist = mnist_images[mnist_indices]
                cats_indices = np.random.choice(cats.shape[0], history_size)
                generation_history_cats = cats[cats_indices]

        # Make and save a test collage
        choice = np.random.choice(mnist_images.shape[0])
        if k.image_data_format() == 'channels_first':
            mnist_in = mnist_images[choice].reshape((1, 1, 28, 28))
        else:
            mnist_in = mnist_images[choice].reshape((1, 28, 28, 1))
        cat_out = generator_cats.predict(mnist_in)
        mnist_cyc_out = generator_mnist.predict(cat_out)
        choice = np.random.choice(cats.shape[0])
        if k.image_data_format() == 'channels_first':
            cat_in = cats[choice].reshape((1, 1, 28, 28))
        else:
            cat_in = cats[choice].reshape((1, 28, 28, 1))
        mnist_out = generator_mnist.predict(cat_in)
        cat_cyc_out = generator_cats.predict(mnist_out)
        mnist_test_images = np.concatenate((prettify(mnist_in), prettify(cat_out), prettify(mnist_cyc_out)), axis=1)
        cat_test_images =  np.concatenate((prettify(cat_in), prettify(mnist_out), prettify(cat_cyc_out)), axis=1)
        test_collage = np.concatenate((mnist_test_images, cat_test_images), axis=0)
        test_collage = Image.fromarray(test_collage, mode='L')
        test_collage.save(os.path.join(SAVEPATH, 'images', str(epoch-1)+'.jpg'))

        for batch in range(100):
            # Get batch.
            mnist_indices = np.random.choice(mnist_images.shape[0], batch_size)
            mnist_batch_real = mnist_images[mnist_indices]
            cats_indices = np.random.choice(cats.shape[0], batch_size)
            cats_batch_real = cats[cats_indices]

            # Update history with new generated images.
            mnist_batch_gen = generator_mnist.predict_on_batch(cats_batch_real)
            cats_batch_gen = generator_cats.predict_on_batch(mnist_batch_real)
            generation_history_mnist = np.concatenate((generation_history_mnist[batch_size:], mnist_batch_gen))
            generation_history_cats = np.concatenate((generation_history_cats[batch_size:], cats_batch_gen))

            # Train discriminators.
            real_label = np.ones(batch_size)
            fake_label = np.zeros(batch_size)

            mnist_discrim_loss.append(discriminator_mnist.train_on_batch(np.concatenate((generation_history_mnist[:batch_size], mnist_batch_real)),
                                            np.concatenate((fake_label, real_label))))

            cats_discrim_loss.append(discriminator_cats.train_on_batch(np.concatenate((generation_history_cats[:batch_size], cats_batch_real)),
                                            np.concatenate((fake_label, real_label))))

            # Train generators.
            loss = gen_trainer.train_on_batch([cats_batch_real, mnist_batch_real], [real_label, real_label, mnist_batch_real, cats_batch_real])

            cats_gen_loss.append(loss[0])
            mnist_gen_loss.append(loss[1])
            mnist_cyc_loss.append(loss[2])
            cats_cyc_loss.append(loss[3])

            if (batch%100 == 0):
                print("\nBatch", batch,
                      "\nMNIST Discriminator Loss:", mnist_discrim_loss[-1],
                      "\nCats Discriminator Loss:", cats_discrim_loss[-1],
                      "\nMNIST Generator Loss:", mnist_gen_loss[-1],
                      "\nCats Generator Loss:", cats_gen_loss[-1],
                      "\nMNIST Cyclic Loss:", mnist_cyc_loss[-1],
                      "\nCats Cyclic Loss:", cats_cyc_loss[-1])

    # Save models.
    generator_cats.save(os.path.join(SAVEPATH, 'generator_cats.h5'))
    generator_mnist.save(os.path.join(SAVEPATH, 'generator_mnist.h5'))
    discriminator_cats.save(os.path.join(SAVEPATH, 'discriminator_cats.h5'))
    discriminator_mnist.save(os.path.join(SAVEPATH, 'discriminator_mnist.h5'))
    # Save training history.
    output_dict = {
        'mnist_discrim_loss' : [str(loss) for loss in mnist_discrim_loss],
        'cats_discrim_loss' : [str(loss) for loss in cats_discrim_loss],
        'mnist_gen_loss' : [str(loss) for loss in mnist_gen_loss],
        'cats_gen_loss' : [str(loss) for loss in cats_gen_loss],
        'mnist_cyc_loss' : [str(loss) for loss in mnist_cyc_loss],
        'cats_cyc_loss' : [str(loss) for loss in cats_cyc_loss]
    }

    with open(os.path.join(SAVEPATH, 'log.txt'), 'w') as f:
        json.dump(output_dict, f, indent=4)


if __name__ == "__main__":
    test_cyclegan()
    print('hello :D')
