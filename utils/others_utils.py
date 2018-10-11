# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018 by Xavier Corredor Llano, SMByC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import tempfile
from subprocess import call
from osgeo import gdal

from qgis.core import QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsProject, QgsCoordinateTransform

from pca4cd.utils.qgis_utils import get_file_path_of_layer


def mask(input_list, boolean_mask):
    """Apply boolean mask to input list

    Args:
        input_list (list): Input list for apply mask
        boolean_mask (list): The boolean mask list

    Examples:
        >>> mask(['A','B','C','D'], [1,0,1,0])
        ['A', 'C']
    """
    return [i for i, b in zip(input_list, boolean_mask) if b]


def clip_raster_with_shape(target_layer, shape_layer, out_path, dst_nodata=None):
    target_file = get_file_path_of_layer(target_layer)
    filename, ext = os.path.splitext(out_path)
    tmp_file = filename + "_tmp" + ext
    # set the nodata
    dst_nodata = "-dstnodata {}".format(dst_nodata) if dst_nodata is not None else ""
    # set the file path for the area of interest
    # check if the shape is a memory layer, then save and used it
    if get_file_path_of_layer(shape_layer).startswith("memory"):
        tmp_memory_fd, tmp_memory_file = tempfile.mkstemp(prefix='memory_layer_', suffix='.gpkg')
        QgsVectorFileWriter.writeAsVectorFormat(shape_layer, tmp_memory_file, "UTF-8", shape_layer.crs(), "GPKG")
        os.close(tmp_memory_fd)
        shape_file = tmp_memory_file
    else:
        shape_file = get_file_path_of_layer(shape_layer)
    # clipping in shape
    return_code = call('gdalwarp -multi -wo NUM_THREADS=ALL_CPUS --config GDALWARP_IGNORE_BAD_CUTLINE YES'
                       ' -cutline "{}" {} "{}" "{}"'.format(shape_file, dst_nodata, target_file, tmp_file), shell=True)
    # create convert coordinates
    crsSrc = QgsCoordinateReferenceSystem(shape_layer.crs())
    crsDest = QgsCoordinateReferenceSystem(target_layer.crs())
    xform = QgsCoordinateTransform(crsSrc, crsDest, QgsProject.instance())
    # trim the boundaries using the maximum extent for all features
    box = []
    for f in shape_layer.getFeatures():
        g = f.geometry()
        g.transform(xform)
        f.setGeometry(g)
        if box:
            box.combineExtentWith(f.geometry().boundingBox())
        else:
            box = f.geometry().boundingBox()
    # intersect with the rater file extent
    box = box.intersect(target_layer.extent())
    # trim
    gdal.Translate(out_path, tmp_file, projWin=[box.xMinimum(), box.yMaximum(), box.xMaximum(), box.yMinimum()])
    # clean tmp file
    if get_file_path_of_layer(shape_layer).startswith("memory") and os.path.isfile(tmp_memory_file):
        os.remove(tmp_memory_file)
    if os.path.isfile(tmp_file):
        os.remove(tmp_file)

    if return_code == 0:  # successfully
        return True
    else:
        return False

