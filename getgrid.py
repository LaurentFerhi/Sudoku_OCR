import numpy as np
from keras.models import load_model

import cv2
from PIL import Image, ImageChops
from skimage.transform import resize
import matplotlib.pyplot as plt

import operator
import warnings
warnings.filterwarnings('ignore')

# Load classifier
clf_trained = load_model("CNN_digit_model.h5")

def show_digits(digits, colour=255):
    rows = []
    with_border = [
        cv2.copyMakeBorder(img.copy(), 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, colour) 
        for img in digits
        ]
    for i in range(9):
        row = np.concatenate(with_border[i * 9:((i + 1) * 9)], axis=1)
        rows.append(row)
    img = np.concatenate(rows)
    return img


def pre_process_image(img, skip_dilate=False):
    """
    Uses a blurring function, adaptive thresholding and dilation to expose the 
    main features of an image.
    """

    # Gaussian blur with a kernal size (height, width) of 9.
    proc = cv2.GaussianBlur(img.copy(), (9, 9), 0)
    # Adaptive threshold using 11 nearest neighbour pixels
    proc = cv2.adaptiveThreshold(
        proc, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
    
    # Invert colours, so gridlines have non-zero pixel values.
    proc = cv2.bitwise_not(proc, proc)

    if not skip_dilate:
        # Dilate the image to increase the size of the grid lines.
        kernel = np.array([[0., 1., 0.], [1., 1., 1.], [0., 1., 0.]],np.uint8)
        proc = cv2.dilate(proc, kernel)
    
    return proc


def find_corners_of_largest_polygon(img):
    """
    Finds the 4 extreme corners of the largest contour in the image.
    """
    opencv_version = cv2.__version__.split('.')[0]
    # Find contours
    if opencv_version == '3':
        _, contours, h = cv2.findContours(img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)  
    else:
        contours, h = cv2.findContours(img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) 
    contours = sorted(contours, key=cv2.contourArea, reverse=True) 
    polygon = contours[0]  # Largest image

    bottom_right, _ = max(
        enumerate([pt[0][0] + pt[0][1] for pt in polygon]), 
        key=operator.itemgetter(1)
        )
    top_left, _ = min(
        enumerate([pt[0][0] + pt[0][1] for pt in polygon]), 
        key=operator.itemgetter(1)
        )
    bottom_left, _ = min(
        enumerate([pt[0][0] - pt[0][1] for pt in polygon]), 
        key=operator.itemgetter(1)
        )
    top_right, _ = max(
        enumerate([pt[0][0] - pt[0][1] for pt in polygon]), 
        key=operator.itemgetter(1)
        )

    # Return an array of all 4 points using the indices
    four_points = [
        polygon[top_left][0], 
        polygon[top_right][0], 
        polygon[bottom_right][0], 
        polygon[bottom_left][0]
        ]

    return four_points
    


def distance_between(p1, p2):
    """
    Returns the scalar distance between two points
    """
    a = p2[0] - p1[0]
    b = p2[1] - p1[1]
    return np.sqrt((a ** 2) + (b ** 2))


def crop_and_warp(img, crop_rect):
    """
    Crops and warps a rectangular section from an image into a square of similar size.
    """

    # Rectangle described by top left, top right, bottom right and bottom left points
    top_left, top_right, bottom_right, bottom_left = crop_rect[0], crop_rect[1], crop_rect[2], crop_rect[3]

    # Set type to float32 or `getPerspectiveTransform` will return an error
    src = np.array([top_left, top_right, bottom_right, bottom_left], dtype='float32')

    # Get the longest side in the rectangle
    side = max([
        distance_between(bottom_right, top_right),
        distance_between(top_left, bottom_left),
        distance_between(bottom_right, bottom_left),
        distance_between(top_left, top_right)
    ])

    # Describe a square with side of the calculated length, this is the new perspective we want to warp to
    dst = np.array([[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]], dtype='float32')

    # Gets the transformation matrix
    m = cv2.getPerspectiveTransform(src, dst)

    # Performs the transformation on the original image
    return cv2.warpPerspective(img, m, (int(side), int(side)))


def infer_grid(img):
    """
    Infers 81 cell grid from a square image.
    """
    squares = []
    side = img.shape[:1]
    side = side[0] / 9

    # list reading left-right instead of top-down.
    for j in range(9):
        for i in range(9):
            p1 = (i * side, j * side)  # Top left corner of a bounding box
            p2 = ((i + 1) * side, (j + 1) * side)  # Bottom right corner of bounding box
            squares.append((p1, p2))
    return squares


def cut_from_rect(img, rect):
    """
    Cuts a rectangle from an image using the top left and bottom right points.
    """
    return img[int(rect[0][1]):int(rect[1][1]), int(rect[0][0]):int(rect[1][0])]

def centre_pad(length, size):
    """
    Handles centering for a given length that may be odd or even
    """
    if length % 2 == 0:
        side1 = int((size - length) / 2)
        side2 = side1
    else:
        side1 = int((size - length) / 2)
        side2 = side1 + 1
    return side1, side2

def scale_and_centre(img, size, margin=0, background=0):
    """
    Scales and centres an image onto a new background square.
    """
    h, w = img.shape[:2]

    if h > w:
        t_pad = int(margin / 2)
        b_pad = t_pad
        ratio = (size - margin) / h
        w = int(ratio*w)
        h = int(ratio*h)
        l_pad, r_pad = centre_pad(w, size)
    else:
        l_pad = int(margin / 2)
        r_pad = l_pad
        ratio = (size - margin) / w
        w = int(ratio*w)
        h = int(ratio*h)
        t_pad, b_pad = centre_pad(h, size)

    img = cv2.resize(img, (w, h))
    img = cv2.copyMakeBorder(
        img, t_pad, b_pad, l_pad, r_pad, cv2.BORDER_CONSTANT, None, background
        )
    return cv2.resize(img, (size, size))


def find_largest_feature(inp_img, scan_tl=None, scan_br=None):
    """
    Uses the fact the `floodFill` function returns a bounding box of the area it 
    filled to find the biggest connected pixel structure in the image. 
    Fills this structure in white, reducing the rest to black.
    """
    img = inp_img.copy()  # Copy the image, leaving the original untouched
    height, width = img.shape[:2]

    max_area = 0
    seed_point = (None, None)

    if scan_tl is None:
        scan_tl = [0, 0]

    if scan_br is None:
        scan_br = [width, height]

    # Loop through the image
    for x in range(scan_tl[0], scan_br[0]):
        for y in range(scan_tl[1], scan_br[1]):
        # Only operate on light or white squares
            if img.item(y, x) == 255 and x < width and y < height: 
                area = cv2.floodFill(img, None, (x, y), 64)
                if area[0] > max_area:  # Gets the maximum bound area which should be the grid
                    max_area = area[0]
                seed_point = (x, y)

    # Colour everything grey (compensates for features outside of our middle scanning range
    for x in range(width):
        for y in range(height):
            if img.item(y, x) == 255 and x < width and y < height:
                cv2.floodFill(img, None, (x, y), 64)

    mask = np.zeros((height + 2, width + 2), np.uint8)  # Mask that is 2 pixels bigger than the image

    # Highlight the main feature
    if all([p is not None for p in seed_point]):
        cv2.floodFill(img, mask, seed_point, 255)

    top, bottom, left, right = height, 0, width, 0

    for x in range(width):
        for y in range(height):
            if img.item(y, x) == 64:  # Hide anything that isn't the main feature
                cv2.floodFill(img, mask, (x, y), 0)

            # Find the bounding parameters
            if img.item(y, x) == 255:
                top = y if y < top else top
                bottom = y if y > bottom else bottom
                left = x if x < left else left
                right = x if x > right else right

    bbox = [[left, top], [right, bottom]]
    return img, np.array(bbox, dtype='float32'), seed_point


def extract_digit(img, rect, size):
    """
    Extracts a digit (if one exists) from a Sudoku square.
    """

    digit = cut_from_rect(img, rect)  # Get the digit box from the whole square

    # Use fill feature finding to get the largest feature in middle of the box
    h, w = digit.shape[:2]
    margin = int(np.mean([h, w]) / 2.5)
    _, bbox, seed = find_largest_feature(digit, [margin, margin], [w - margin, h - margin])
    digit = cut_from_rect(digit, bbox)

    # Scale and pad the digit so that it fits machine learning inputs
    w = bbox[1][0] - bbox[0][0]
    h = bbox[1][1] - bbox[0][1]

    # Ignore any small bounding boxes
    if w > 0 and h > 0 and (w * h) > 100 and len(digit) > 0:
        return scale_and_centre(digit, size, 4)
    else:
        return np.zeros((size, size), np.uint8)


def get_digits(img, squares, size):
    """
    Extracts digits from their cells and builds an array
    """
    digits = []
    img = pre_process_image(img.copy(), skip_dilate=True)
    #cv2.imshow('img', img)
    for square in squares:
        digits.append(extract_digit(img, square, size))
    return digits

def extract_sudoku(image_path):
    """
        Find grid from image
    """
    original = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    processed = pre_process_image(original)
    
    corners = find_corners_of_largest_polygon(processed)
    cropped = crop_and_warp(original, corners)

    squares = infer_grid(cropped)
    #print(squares)
    digits = get_digits(cropped, squares, 28)
    #print(digits)
    final_image = show_digits(digits)
    return final_image


def digit_predict(image):
    """
    Recognize digit from grid square image
    """
    # remove white borders
    image_clean = image.copy()
    image_clean[0, :] = 0
    image_clean[27, :] = 0
    image_clean[:, 0] = 0
    image_clean[:, 27] = 0
    
    X_image = image_clean.reshape(1, 28, 28, 1)
    y_image_pred = clf_trained.predict(X_image)
    y_image_pred_classes = np.argmax(y_image_pred, axis=1)[0]
    
    # Convert to flatten vector with 0 to 255 vals and make prediction
    return y_image_pred_classes

def get_grid(image_path, display=False):
    """
    Returns the sodoku grid array from image
    """
    sudoku = extract_sudoku(image_path)
    sudoku = resize(sudoku, (252,252))

    if display:
        plt.matshow(sudoku)
     
    grid = np.zeros([9,9])
    for i in range(9):
        for j in range(9):
            # image 28x28
            image = sudoku[i*28:(i+1)*28,j*28:(j+1)*28]
            if image.sum() >105:    
                grid[i][j] = digit_predict(image)
            else:
                grid[i][j] = 0
    grid =  grid.astype(int)
    
    return grid
