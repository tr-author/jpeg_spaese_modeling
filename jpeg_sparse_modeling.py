import math
import numpy as np
import pandas as pd
import cv2
import matplotlib.pyplot as plt
from pprint import pprint
from cvxpy import *
import time
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

N = 8

np.set_printoptions(suppress=True)


class image_JPEG:
    def __init__(self,N):
        self.quantizer_table = \
            np.array([ 16, 11, 10, 16,  24,  40,  51,  61,
                       12, 12, 14, 19,  26,  58,  60,  55,
                       14, 13, 16, 24,  40,  57,  69,  56,
                       14, 17, 22, 29,  51,  87,  80,  62,
                       18, 22, 37, 56,  68, 109, 103,  77,
                       24, 35, 55, 64,  81, 104, 113,  92,
                       49, 64, 78, 87, 103, 121, 120, 101,
                      72, 92, 95, 98, 112, 100, 103,  99 ])
        
        self.N = N
        self.phi = np.array([self.phi_k(k) for k in range(N)])
        self.sparse_num = 0
        
    def phi_k(self,k):
        if k == 0:
            return np.ones(self.N) / math.sqrt(self.N)
        else:
            return math.sqrt(2/self.N)*np.cos(((2*(np.arange(self.N))+1)*k*math.pi)/(2*self.N))
    
    def compress(self,img):
        img_N_division = []
        x,y = img.shape
        if x %8 != 0 or y %8 != 0:
            print("Error : image must be square, and its size must be divided 8")
            return -1
        
        for i in range(y//8):
            for j in range(x//8):
                img_N_division.append(img[self.N*i:self.N*(i+1),self.N*j:self.N*(j+1)])


        for i in range(y//8):
            for j in range(x//8):
                qdct_coef_N_division,compressed_img_N_division = self.calculate(img_N_division[i*(y//N)+j])
                if j == 0:
                    compressed_img_N_row = compressed_img_N_division
                    qdct_coef_N_row = qdct_coef_N_division
                else:
                    compressed_img_N_row = np.concatenate([compressed_img_N_row, compressed_img_N_division], 1)
                    qdct_coef_N_row = np.concatenate([qdct_coef_N_row, qdct_coef_N_division], 1)
            if i == 0:
                compressed_img = compressed_img_N_row
                qdct_coef = qdct_coef_N_row
            else:
                compressed_img = np.concatenate([compressed_img,  compressed_img_N_row])
                qdct_coef = np.concatenate([qdct_coef, qdct_coef_N_row])
        
        compressed_img = correct_abnormal_value(compressed_img.astype(dtype=int))
        qdct_coef = qdct_coef.astype(dtype=int)
        return qdct_coef, compressed_img

    def calculate(self,img):
        print(img.shape)
        dct_coef = self.dct(img)
        
        quantized_dct = self.quantize(dct_coef)

        self.sparse_num += quantized_dct.size-np.count_nonzero(quantized_dct)
        inv_quantized_dct = self.inv_quantize(quantized_dct)

        #inv_quantized_dct = np.array(np.split(inv_quantized_dct,8))
        invdct_coef = self.idct(inv_quantized_dct)
        
        return quantized_dct,invdct_coef

    def get_num_nonzero_in_arr(arr):
        arr = arr.flatten()
        return len(arr) - np.count_nonzero(arr)
    
    def dct(self,img):
        img -= 128
        return np.dot(np.dot(self.phi,img),self.phi.T)
    def idct(self,inquimg):
        return np.round(np.dot(np.dot(self.phi.T,inquimg),self.phi)) + 128
    
    def quantize(self,dctimg):
        return np.array(np.split(np.round(np.array(dctimg.flatten()) / self.quantizer_table),8))
    def inv_quantize(self,quimg):
        return np.array(np.split(np.array(quimg.flatten()) * self.quantizer_table,8))
    
    def compressed_img(self,img,is_quantize=True):
        image_list = []
        x,y = img.shape

        for i in range(y//8):
            for j in range(x//8):
                im = img[self.N*i:self.N*(i+1),self.N*j:self.N*(j+1)]
                image_list.append(im)

        for i in range(y//8):
            for j in range(x//8):
                if is_quantize==True:
                    dct_img = np.array(np.split(self.quantize(np.array(np.split(self.dct(image_list[i*(y//N)+j]),8))),8))
                else:
                    dct_img = self.dct(image_list[i*(y//N)+j])
                
                if j == 0:
                    pre_coef = dct_img
                else:
                    pre_coef = np.concatenate([pre_coef, dct_img], 1)
            if i == 0:
                DCT_img = pre_coef
            else:
                DCT_img = np.concatenate([DCT_img,  pre_coef])
            
        DCT_img = DCT_img.astype(dtype=int)
        return DCT_img


class image_sparse:
    def __init__(self,N):
        self.N = N
        self.phi = np.zeros((N**2,N**2))
        self.sparse_num = 0
        for i in range(N**2):
            for j in range(N**2):
                self.phi[i][j] = self.phi_k_i(j//N,i//N)*self.phi_k_i(j%N,i%N)

    def phi_k_i(self,k,i):
        if k == 0:
            return 1 / math.sqrt(self.N)
        else:
            return math.sqrt(2/self.N)*math.cos(((2*i+1)*k*math.pi)/(2*self.N))
        
    
    def compress(self,img):
        img_N_division = []
        x,y = img.shape
        if x %8 != 0 or y %8 != 0:
            print("Error : Error : image must be square, and its size must be divided 8")
            return -1
        
        for i in range(y//8):
            for j in range(x//8):
                img_N_division.append(img[self.N*i:self.N*(i+1),self.N*j:self.N*(j+1)])

        for i in range(y//8):
            for j in range(x//8):
                dct_coef_N_division,compressed_img_N_division = self.calculate(image_list[i*(y//N)+j])

                if j == 0:
                    compressed_img_row = compressed_img_N_division
                    dct_coef_row = dct_coef_N_division
                else:
                    compressed_img_row = np.concatenate([compressed_img_row, compressed_img_N_division], 1)
                    dct_coef_row = np.concatenate([dct_coef_row, dct_coef_N_division], 1)
            if i == 0:
                compressed_img = compressed_img_row
                dct_coef = dct_coef_row
            else:
                compressed_img = np.concatenate([compressed_img,  compressed_img_row])
                dct_coef = np.concatenate([dct_coef,  dct_coef_row])
            
            print("\r","Progress, ( 1 ~",y//8,")",i+1,end='')

        print("")
            
        compressed_img = correct_abnormal_value(compressed_img.astype(dtype=int))
        dct_coef = dct_coef.astype(dtype=int)
        return dct_coef,compressed_img

    
    def calculate(self,img):
        dct_coef = self.opt_dct_coef(img)
        self.sparse_num += get_num_nonzero_in_arr(dct_coef)
        invdct_coef = self.idct(dct_coef)
        
        return dct_coef,invdct_coef
    
    def get_num_nonzero_in_arr(arr):
        arr = arr.flatten()
        return len(arr) - np.count_nonzero(arr)

    def opt_dct_coef(self,img,lam=1.0):
        #行列Wを生成
        img -= 128
        W = self.phi

        #変数xを定義
        x = Variable(self.N ** 2)
        y = img.flatten()
        #ハイパーパラメータを定義
        lamda = Parameter(nonneg=True)
        lamda.value =lam

        #目的関数を定義
        objective = Minimize(sum_squares((y - W @ x))/(2*N)+ lamda*norm(x, 1))
        p = Problem(objective)

        #最適化計算
        result = p.solve()
        dct_coef = np.round(x.value)
        return np.array(np.split(dct_coef,8)) 
    
    def idct(self,dct_coef):
        invdct = np.dot(self.phi, dct_coef.flatten())
        return np.round(np.split(invdct,8)) + 128
    
    def compressed_img(self,img):
        image_list = []
        x,y = img.shape

        for i in range(y//8):
            for j in range(x//8):
                im = img[self.N*i:self.N*(i+1),self.N*j:self.N*(j+1)]
                image_list.append(im)

        for i in range(y//8):
            for j in range(x//8):
                dct_img = np.array(np.split(self.dct(image_list[i*(y//N)+j]),8))
                
                if j == 0:
                    pre_coef = dct_img
                    
                else:
                    pre_coef = np.concatenate([pre_coef, dct_img], 1)
            if i == 0:
                DCT_img = pre_coef
            else:
                DCT_img = np.concatenate([DCT_img,  pre_coef])
            
            print("\r","calculateing(incredible inefficient progress), ( 1 ~",y//8,")",i+1,end='')

        print("")   
        DCT_img = DCT_img.astype(dtype=int)
        return DCT_img

def calc_entropy(img,is_img):
    l = img.shape[0]
    
    if is_img == False:
        if np.min(img) < 0:
            img -= np.min(img)
  
        histgram = [0]*(np.max(img)+1)
       
    else:
        histgram = [0]*256

    for i in range(l):
        for j in range(l):
            v =img[i, j]
            histgram[v] += 1

    size = img.shape[0] * img.shape[1]
    entropy = 0

    for i in range(len(histgram)):

        p = histgram[i]/size
        if p == 0:
            continue
        entropy -= p*math.log2(p)
    return entropy

def correct_abnormal_value(img):
    l = img.shape[0]
    for i in range(l):
        for j in range(l):
            if img[i,j] < 0:
                img[i,j] = 0
            if img[i,j] > 255:
                img[i,j] = 255

def jpeg_img_test():
    
    img_test = np.array([
    [139,144,149,153,155,155,155,155],
    [144,151,153,156,159,156,156,156],
    [150,155,160,163,158,156,156,156], 
    [159,161,162,160,160,159,159,159],
    [159,161,162,162,162,155,155,155],
    [161,161,161,161,160,157,157,157],
    [162,162,161,163,162,157,157,157],
    [162,162,161,161,163,158,158,158]
    ])

    plt.imshow(img_test,vmin=0, vmax=255)
    plt.gray()

    jpeg_test = JPEG(N)
    #----------------------
    plt.subplot(1,2,1)
    plt.imshow(img_test,vmin=0, vmax=255)
    plt.title("original")
    converted_img = jpeg_test.convertToJPEG(img_test)

    plt.subplot(1,2,2)
    plt.imshow(converted_img,vmin=0,vmax=255)
    plt.title("jpeg converted")
    plt.gray()


    print("\t\tPSNR :",psnr(img_test,converted_img,data_range=255))
    print("\t\tSSIM :",ssim(img_test,converted_img,data_range=255))

def original_jpeg_convert():

    img = cv2.imread('girl.bmp', 0).astype(dtype=int)
    img_= cv2.imread('girl.bmp', 0).astype(dtype=int)
    
    image = image_JPEG(N)

    plt.figure(figsize=(6, 4))
    plt.subplot(1,2,1)
    plt.imshow(img,vmin=0, vmax=255)
    plt.title("original")
    plt.gray()

    qdct_coef, compressed_img = image.compress(img_)

    print("\tnumber of dct with zero as its coefficient",image.sparse_num)
    plt.subplot(1,2,2)
    plt.imshow(compressed_img,vmin=0,vmax=255)
    plt.title("jpeg converted")

    print("\t\tentropy :",calc_entropy(qdct_coef,is_img=False))

    print("\t\tPSNR :",psnr(img,compressed_img,data_range=255))
    print("\t\tSSIM :",ssim(img,compressed_img,data_range=255))

    cv2.imwrite('./jpeg_converted.png', converted_img)

def new_jpeg_convert():

    img = cv2.imread('girl.bmp', 0).astype(dtype=int)

    #----------------------
    sparse = image_sparse(N)

    print("Compress images in JPEG format with L1 regularization")

    plt.figure(figsize=(6, 4))
    plt.subplot(1,2,1)
    plt.imshow(img,vmin=0, vmax=255)
    plt.title("original")
    plt.gray()


    dct_coef,compressed_img = sparse.compress(img)
    #compressed = sparse.compressed_img(img_)
    print("\tnumber of L1 with zero as its coefficient",sparse.sparse_num)

    plt.subplot(1,2,2)
    plt.imshow(converted_img,vmin=0,vmax=255)
    plt.title("JPEG format with L1 regularization")

    print("\t\tentropy :",calc_entropy(dct_coef,is_img=False))

    img = cv2.imread('girl.bmp', 0).astype(dtype=int)

    print("\t\tPSNR :",psnr(img,compressed_img,data_range=255))
    print("\t\tSSIM :",ssim(img,compressed_img,data_range=255))

    cv2.imwrite('./new_jpeg.bmp', converted_img)

    

if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    #jpeg_img_test()
    #plt.show()
    original_jpeg_convert()
    print("-----------------------------------------------------")
    new_jpeg_convert()
    plt.show()
