#!/usr/bin/env python
# encoding: utf-8
from decimal import Decimal as D
"""
package.py - shipping/cargo related calculations based on a unit of shipping (box, crate, package)

Created by Maximillian Dornseif on 2006-12-02.
Copyright HUDORA GmbH 2006, 2007, 2010
You might consider this BSD-Licensed.
"""

class Package(object):
    """Represents a package as used in cargo/shipping aplications."""

    def __init__(self, size, title='', upc='', value=0, weight=D('0.0'), nosort=False):
        """Generates a new Package object.

        The size can be given as an list of integers or an string where the sizes are
        separated by the letter 'x':
        >>> Package((300, 400, 500))
        <Package 500x400x300>
        >>> Package('300x400x500')
        <Package 500x400x300>
        """
        self.weight = weight
        if "x" in size:
            self.height, self.width, self.length = [float(x) for x in size.split('x')]
        else:
            self.height, self.width, self.length = size
        if not nosort:
            (self.height, self.width, self.length) = sorted((float(self.height), float(self.width),
                                                             float(self.length)), reverse=True)
        self.volume = self.height * self.width * self.length
        self.size = (self.height, self.width, self.length)
        self.title = title
        self.value = value
        self.upc = upc

    def _get_gurtmass(self):
        """'gurtamss' is the circumference of the box plus the length - which is often used to
            calculate shipping costs.

            >>> Package((100,110,120)).gurtmass
            540
        """

        dimensions = (self.height, self.width, self.length)
        maxdimension = max(dimensions)
        otherdimensions = list(dimensions)
        del otherdimensions[otherdimensions.index(maxdimension)]
        return maxdimension + 2 * (sum(otherdimensions))
    gurtmass = property(_get_gurtmass)

    def hat_gleiche_seiten(self, other):
        """Prüft, ob other mindestens eine gleich grosse Seite mit self hat."""

        meineseiten = set([(self.height, self.width), (self.height, self.length), (self.width, self.length)])
        otherseiten = set([(other.height, other.width), (other.height, other.length),
                           (other.width, other.length)])
        return bool(meineseiten.intersection(otherseiten))

    def girth_plus_length(self):
        return ((self.height + self.width) * 2) + self.length

    def __getitem__(self, key):
        """The coordinates can be accessed as if the object is a tuple.
        >>> p = Package((500, 400, 300))
        >>> p[0]
        500
        """
        if key == 0:
            return self.height
        if key == 1:
            return self.width
        if key == 2:
            return self.length
        if isinstance(key, tuple):
            return (self.height, self.width, self.length)[key[0]:key[1]]
        if isinstance(key, slice):
            return (self.height, self.width, self.length)[key]
        return getattr(self, key)

    def __contains__(self, other):
        """Checks if on package fits within an other.

        >>> Package((1600, 250, 480)) in Package((1600, 250, 480))
        True
        >>> Package((1600, 252, 480)) in Package((1600, 250, 480))
        False
        """
        return self[0] >= other[0] and self[1] >= other[1] and self[2] >= other[2]

    def __hash__(self):
        return self.height + (self.width << 16) + (self.length << 32)

    def __eq__(self, other):
        """Package objects are equal if they have exactly the same dimensions.

           Permutations of the dimensions are considered equal:

           >>> Package((100,110,120)) == Package((100,110,120))
           True
           >>> Package((120,110,100)) == Package((100,110,120))
           True
        """
        return (self.height == other.height and self.width == other.width and self.length == other.length)

    def __cmp__(self, other):
        """Enables to sort by Volume."""
        return cmp(self.volume, other.volume)

    def __mul__(self, multiplicand):
        """Package can be multiplied with an integer. This results in the Package beeing
           stacked along the biggest side.

           >>> Package((400,300,600)) * 2
           <Package 600x600x400>
           """
        if self.weight:
            new_weight = self.weight * multiplicand
        else:
            new_weight = None
        return Package((self.height, self.width, self.length * multiplicand), new_weight)

    def __add__(self, other):
        """
            >>> Package((1600, 250, 480)) + Package((1600, 470, 480))
            <Package 1600x720x480>
            >>> Package((1600, 250, 480)) + Package((1600, 480, 480))
            <Package 1600x730x480>
            >>> Package((1600, 250, 480)) + Package((1600, 490, 480))
            <Package 1600x740x480>
            """
        meineseiten = set([(self.height, self.width), (self.height, self.length),
                           (self.width, self.length)])
        otherseiten = set([(other.height, other.width), (other.height, other.length),
                           (other.width, other.length)])
        if not meineseiten.intersection(otherseiten):
            raise ValueError("%s has no fitting sites to %s" % (self, other))
        candidates = sorted(meineseiten.intersection(otherseiten), reverse=True)
        stack_on = candidates[0]
        mysides = [self.height, self.width, self.length]
        mysides.remove(stack_on[0])
        mysides.remove(stack_on[1])
        othersides = [other.height, other.width, other.length]
        othersides.remove(stack_on[0])
        othersides.remove(stack_on[1])

        if self.weight and other.weight:
            new_weight = self.weight + other.weight
        else:
            new_weight = None

        return Package((stack_on[0], stack_on[1], mysides[0] + othersides[0]), new_weight)

    def __str__(self):
        if self.weight:
            return "%.2fx%.2fx%.2f %.2f" % (self.height, self.width, self.length, self.weight)
        else:
            return "%.2fx%.2fx%.2f" % (self.height, self.width, self.length)

    def __repr__(self):
        if self.weight:
            return "<Package %.2fx%.2fx%.2f %.2f>" % (self.height, self.width, self.length, self.weight)
        else:
            return "<Package %.2fx%.2fx%.2f>" % (self.height, self.width, self.length)


def buendelung(kartons, maxweight=31000, maxgurtmass=3000):
    """Versucht Pakete so zu bündeln, so dass das Gurtmass nicht überschritten wird.

    Gibt die gebündelten Pakete und die nicht bündelbaren Pakete zurück.

    >>> buendelung([Package((800, 310, 250)), Package((800, 310, 250)), Package((800, 310, 250)), Package((800, 310, 250))])
    (1, [<Package 800x750x310>], [<Package 800x310x250>])
    >>> buendelung([Package((800, 310, 250)), Package((800, 310, 250)), Package((800, 310, 250)), Package((800, 310, 250)), Package((450, 290, 250)), Package((450, 290, 250))])
    (2, [<Package 800x750x310>, <Package 500x450x290>], [<Package 800x310x250>])
    """
    kartons = list(kartons)

    def buendelung_moeglich(box_a, box_b):
        """Entscheide, ob eine Bündelung der beiden Kartons möglich ist.

        Es kann gebündelt werden, wenn die Summe der Gewichte (falls gepflegt)
        kleiner ist als das maximale Gewicht,
        das Gurtmaß nicht das maximale Gurtmaß übersteigt
        und nicht bereits die maximale Anzahl der Bündelungen erreicht ist.
        """

        if kartons_im_buendel > MAXKARTONSIMBUENDEL:
            return False

        tmp = box_a + box_b
        if tmp.weight > maxweight:
            return False
        elif tmp.gurtmass > maxgurtmass:
            return False
        return True

    MAXKARTONSIMBUENDEL = 6
    if not kartons:
        return 0, [], kartons
    gebuendelt = []
    rest = []
    lastcarton = kartons.pop(0)
    buendel = False
    buendelcounter = 0
    kartons_im_buendel = 1
    while kartons:
        currentcarton = kartons.pop(0)
        # check if 2 dimensions fit and bundling is possible
        if currentcarton.hat_gleiche_seiten(lastcarton) and buendelung_moeglich(lastcarton, currentcarton):
            # new carton has the same size in two dimensions and the sum of both in the third
            lastcarton = lastcarton + currentcarton
            kartons_im_buendel += 1
            if buendel is False:
                # neues Bündel
                buendelcounter += 1
            buendel = True
        else:
            # different sizes, or too big
            if buendel:
                gebuendelt.append(lastcarton)
            else:
                rest.append(lastcarton)
            kartons_im_buendel = 1
            lastcarton = currentcarton
            buendel = False
    if buendel:
        gebuendelt.append(lastcarton)
    else:
        rest.append(lastcarton)
    return buendelcounter, gebuendelt, rest


def pack_in_bins(kartons, versandkarton):
    """Implements Bin-Packing.

    You provide it with a bin size and a list of Package Objects to be bined. Returns a list of lists
    representing the bins with the binned Packages and a list of Packages too big for binning.

    >>> pack_in_bins([Package('135x200x250'), Package('170x380x390'), Package('485x280x590'), Package('254x171x368'), Package('201x172x349'), Package('254x171x368')], \
                     Package('600x400x400'))
    ([[<Package 250x200x135>, <Package 349x201x172>, <Package 368x254x171>], [<Package 368x254x171>, <Package 390x380x170>]], [<Package 590x485x280>])
    """

    import binpack_simple.binpack
    toobig, packagelist, bins, rest = [], [], [], []
    for box in sorted(kartons, reverse=True):
        if box not in versandkarton:
            # passt eh nicht
            toobig.append(box)
        else:
            packagelist.append(box)
    if packagelist:
        bins, rest = binpack_simple.binpack.binpack(packagelist, versandkarton)
    return bins, toobig + rest
