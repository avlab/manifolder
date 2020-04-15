import numpy as np
from numpy.linalg import inv

from sklearn.cluster import KMeans

import manifolder_helper as mh

import functools
print = functools.partial(print, flush=True)


def test():
    print('test function called')


#class LinearRegression(MultiOutputMixin, RegressorMixin, LinearModel):
class Manifolder():
    """
    Implementation of Emperical Intrinsic Geometry (EIG) for time-series.

    Parameters
    ----------
    dim : int, optional, default 3
        The dimension of the underlying manifold.
        This will typically be somewhat smaller than the dimension of the data

    H: int, optional, default 40
        Non-overlapping window length for histogram/empirical densities estimation

    step_size: int, optional, default 5
        Stride between histograms

    nbins: int, optional, default 5
        Number of bins to use when creating histogram

    See Also
    --------

    Notes
    -----

    Examples
    --------
    >>> import numpy as np
    >>> from sklearn.linear_model import LinearRegression
    >>> manifolder = Manifolder().fit(data)
    >>> clusters() = manifolder.clusters()
    """
    def __init__(self, dim=3, H=40, step_size=5, nbins=5, distance_measure=None, n_jobs=None):
        self.Dim = dim
        self.H = H
        self.stepSize = step_size
        self.nbins = nbins

        self.distance_measure = distance_measure

    def fit_transform(self, X):
        """
        Fit (find the underlying manifold).

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            Training data

        Returns
        -------
        self : returns an instance of self.
        """

        ### IMPORTANT - sklearn, and Python / data science in general use the convention where
        ###
        ###  data = [samples, features]
        ###
        ### manifolder takes the data in this semi-standard format, but internally uses the
        ### 'observations as columns' format from the original MATLAB
        ###
        #print('fit was called, not yet implemented')
        self._load_data(X)

        if self.distance_measure is None:
            self._histograms_overlap()
            self._covariances()
            self._embedding()
        elif self.distance_measure == 'euclidian':
            # self._euclidian
            print('not yet implemented')
        elif self.distance_measure == 'euclidian':
            print('not yet implemented')
        return self.Psi  # the final clustering is in Psi
        # self._clustering()

        # sklearn fit() tends to return self
        return self

    def _load_data(self, data):
        """ loads the data, in [samples, nfeatures]
            NOTE - internally, data is stored in the
            format used in the original code """
        self.z = data.T      # time is a function of columns, internally

        self.N = self.z.shape[0]  # will be 8, the number of features

    def _histograms_overlap(self):

        ## Concatenate 1D histograms (marginals) of each sensor in short windows
        z_hist_list = []     # in Python, lists are sometimes easier than concatinate

        print('calculating histograms for', self.N, 'dimensions (univariate timeseries) ', end='')

        # for dim=1:N
        for dim in range(self.N):      # loop run standard Python indexing, starting at dim = 0
            print('.', end='')
            series = self.z[dim, :]    # grab a row of data

            # NOTE, MATLAB and python calculate histograms differently
            # MATLAB uses nbins values, as bins centerpoints, and
            # Python uses nbins+1 values, to specify the bin endpoints

            # note, hist_bins will always be [0 .25 .5 .75 1], in MATLAB
            # equivalent for python hist is
            #   [-0.12   0.128  0.376  0.624  0.872  1.12 ]
            hist_bins = mh.histogram_bins_centered(series, self.nbins)

            z_hist_dim_list = []

            # for i=1:floor((size(z,2)-H)/stepSize)
            i_range = int(np.floor(self.z.shape[1] - self.H) / self.stepSize)
            for i in range(i_range):
                # interval = z(dim, 1 + (i - 1) * stepSize: (i - 1) * stepSize + H);
                interval = series[i * self.stepSize:i * self.stepSize + self.H]

                # take the histogram here, and append it ... should be nbins values
                # first value returned by np.histogram the actual histogram
                #
                #  NOTE!!! these bins to not overlap completely with the MATLAB version,
                #   but are roughly correct ... probably exact boundaries are not the same,
                #   would need to look into this ...
                #
                hist = np.histogram(interval, hist_bins)[0]
                z_hist_dim_list.append(hist)

            # convert from a list, to array [nbins x (series.size/stepSize?)]
            z_hist_dim = np.array(z_hist_dim_list).T

            # z_hist = [z_hist; z_hist_dim];
            z_hist_list.append(z_hist_dim)

        # convert from list back to numpy array
        self.z_hist = np.concatenate(z_hist_list)

        print(' done')

    def _covariances(self):
        print('computing local covariances ', end='')

        ## Configuration
        # ncov = 10    # (previous value) size of neighborhood for covariance
        ncov = 40  # size of neighborhood for covariance

        self.z_mean = np.zeros_like(self.z_hist)      # Store the mean histogram in each local neighborhood

        # NOTE, original matlab call should have used N * nbins ... length(hist_bins) works fine in MATLAB,
        # but in python hist_bins has one more element than nbins, since it defines the boundaries ...

        # inv_c = zeros(N*length(hist_bins), N*length(hist_bins), length(z_hist))
        # Store the inverse covariance matrix of histograms in each local neighborhood
        self.inv_c = np.zeros((self.N * self.nbins, self.N * self.nbins, self.z_hist.shape[1]))

        # precalculate the values over which i will range ...
        # this is like 40 to 17485 (inclusive) in python
        # 41 to 17488 in MATLAB ... (check?)
        irange = range(ncov, self.z_hist.shape[1] - ncov - 1)

        # instead of waitbar, print .......... to the screen during processing
        waitbar_increments = int(irange[-1] / 10)

        for i in irange:
            if i % waitbar_increments == 0:
                print('.', end='')
            # not sure of the final number boundary for the loop ...
            # win = z_hist(:, i-ncov:i+ncov-1)
            # TODO - Alex, is this the right range in MATLAB?
            win = self.z_hist[:, i - ncov:i + ncov]   # python, brackets do not include end, in MATLAB () includes end

            ###
            ### IMPORTANT - the input to the cov() call in MATLAB is TRANSPOSED compared to numpy
            ###    cov(win.T) <=> np.cov(win)
            ###
            #
            # # Python example
            # A = np.array([[0, 1 ,2],[3, 4, 5]])
            # print(A)
            # print(np.cov(A.T))
            #
            # % MATLAB example
            # >> A = [[0 1 2];[3 4 5]]
            # >> cov(A)
            #
            # TODO - lol, don't use 40x40, use a different number of bins, etc.
            c = np.cov(win)

            #  De-noise via projection on "known" # of dimensions
            #    [U S V] = svd(c); # matlab
            # python SVD looks very similar to MATLAB:
            #  https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.svd.html
            #    factors a such that a == U @ S @ Vh
            U, S, V = mh.svd_like_matlab(c)

            # inverse also works the same in Python as MATLAB ...
            # matlab:
            # >> X = [1 0 2; -1 5 0; 0 3 -9]
            # >> Y = inv(X)
            #
            #     0.8824   -0.1176    0.1961
            #     0.1765    0.1765    0.0392
            #     0.0588    0.0588   -0.0980
            #
            # Python:
            # X = np.array([[1, 0, 2],[-1, 5, 0],[0, 3, -9]])
            # Y = inv(X)
            #
            # [[ 0.8824 -0.1176  0.1961]
            #  [ 0.1765  0.1765  0.0392]
            #  [ 0.0588  0.0588 -0.098 ]]

            # inv_c(:,:,i) = U(:,1:Dim) * inv(S(1:Dim,1:Dim)) * V(:,1:Dim)'  # matlab
            self.inv_c[:, :, i] = U[:, :self.Dim] @ inv(S[:self.Dim, :self.Dim]) @ V[:, :self.Dim].T    # NICE!

            # z_mean(:, i) = mean(win, 2); # matlab
            self.z_mean[:, i] = np.mean(win, 1)

        print(' done')

    def _embedding(self):
        ###
        ### Part I
        ###

        ## Configuration

        # the variable m defines some subset of the data, to make computation faster;
        # this could be various values (10% of the data, all the data, etc.), as long
        # as it is not GREATER than the length of data.
        #   For the smallest change, setting to min 4000 or the data size

        #m = 4000                  # starting point for sequential processing/extension
        m = np.min((4000,self.z_mean.shape[1]))
        print('using',m,'for variable m')

        data = self.z_mean.T      # set the means as the input set
        M = data.shape[0]

        # Choose subset of examples as reference
        # this is 'take m (4000) random values from z_mean, and sort them
        # subidx = sort(randperm(size(z_mean, 2), m))
        # Choose first m examples as reference (commented out, don't do this
        # subidx = 1:m;
        subidx = np.arange(self.z_mean.shape[1])
        np.random.shuffle(subidx)      # shuffle is inplace in python
        subidx = subidx[:m]            # take a portion of the data
        subidx.sort()                  # sort is also in place ...

        # dataref = data(subidx,:)
        dataref = data[subidx, :]

        ##
        # Affinity matrix computation

        print('computing Dis matrix ', end='')

        waitbar_increments = m // 10
        Dis = np.zeros((M, m))

        for j in range(m):
            if j % waitbar_increments == 0:
                print('.', end='')

            tmp1 = self.inv_c[:, :, subidx[j]] @ dataref[j, :].T     # 40, in Python

            a2 = np.dot(dataref[j, :], tmp1)     # a2 is a scalar
            b2 = np.sum(data * (self.inv_c[:, :, subidx[j]] @ data.T).T, 1)
            ab = data @ tmp1                     # only @ works here

            # this tiles the matrix ... repmat is like np.tile
            # Dis[:,j] = repmat[a2, M, 1] + b2 - 2*ab
            Dis[:, j] = (np.tile(a2, [M, 1])).flatten() + b2 - 2*ab

        print('done!')

        ## Anisotropic kernel

        print('aniostropic kernel ... ', end='')

        ep = np.median(np.median(Dis, 0))   # default scale - should be adjusted for each new realizations

        A = np.exp(-Dis / (4*ep))
        W_sml = A.T @ A
        d1 = np.sum(W_sml, 0)
        A1 = A / np.tile(np.sqrt(d1), [M, 1])
        W1 = A1.T @ A1

        d2 = np.sum(W1, 0)
        A2 = A1 / np.tile(np.sqrt(d2), [M, 1])
        W2 = A2.T @ A2

        D = np.diag(np.sqrt(1 / d2))

        ###
        ### Part II
        ###

        # Compute eigenvectors

        # in numpy,
        # from numpy import linalg as LA
        # w, v = LA.eig(np.diag((1, 2, 3)))
        #  v are the values, diagonal in a matrix, and w are the eigenvectors

        # [V, E] = eigs(W2, 10) Matlab
        V, E = mh.eigs_like_matlab(W2, 10)  # think this is correct now ...

        # print('V.shape', V.shape)
        # print('E.shape', E.shape)

        # python np.sum(A,0) <=> matlab sum(A)
        # in matlab, srted are the values of sum(E) sorted (in descending order)
        # and IE are the indices that sorted them
        # [srtdE, IE] = sort(sum(E), 'descend')

        # this is python eqivalent ... note that IE will have values one less than the MATLAB, because zero indexing
        # TODO - is this sorted right?
        IE = np.sum(E, 0).argsort()[::-1]   # find the indices to sort, and reverse them
        srtdE = np.sum(E, 0)[IE]

        # Phi = D @ V(:, IE(1, 2:10))
        Phi = D @ V[:, IE[1:]]

        print('done')

        ###
        ### Part III
        ###

        # TODO - not necessary?  (Independent coordinates?)

        # Extend reference embedding to the entire set
        print('extending embedding (building Psi) ... ', end='')

        Psi_list = []   # holds all the psi_i values

        omega = np.sum(A2, 1)
        A2_nrm = A2 / np.tile(omega.reshape([-1, 1]), [1, m])   # omega needed to be shaped as a column

        # for i=1:size(Phi,2)
        for i in range(Phi.shape[1]):
            # this line is strange ... order of operations for @?, what is the offset?
            psi_i = A2_nrm @ Phi[:, i] / np.sqrt((srtdE[i + 1]))
            # [Psi, psi_i]
            Psi_list.append(psi_i)

        # convert Psi_list back into an array, shaped like MATLAB version
        self.Psi = np.array(Psi_list).T

        # psi have have very small imaginary values ...
        # cast to real here, but need to check
        self.Psi = np.real(self.Psi)

        # print('Psi.shape', Psi.shape)

        print('done')

        # Since close to a degenerate case - try to rotate according to:
        # A. Singer and R. R. Coifman, "Spectral ICA", ACHA 2007.
        #

    def _clustering(self):

        # Cluster embedding and generate figures and output files
        # ***************************************************************@

        import matplotlib.pyplot as plt

        # Configuration
        numClusters = 7           # NOTE, this was previously 14 (too many!)
        intrinsicDim = self.Dim   # can be varied slightly but shouldn't be much larger than Dim

        ## Clusters
        # IDX = kmeans(Psi(:, 1:intrinsicDim), numClusters)

        # Python kmeans see
        # https://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.cluster.vq.kmeans.html
        # scipy.cluster.vq.kmeans(obs, k_or_guess, iter=20, thresh=1e-05)
        #
        #  note, python expects each ROW to be an observation, looks the same a matlap
        #

        print('running k-means')

        kmeans = KMeans(n_clusters=numClusters).fit(self.Psi[:, :intrinsicDim])
        self.IDX = kmeans.labels_

        # think that x_ref[1,:] is just
        xref1 = self.z[0, :]
        xref1 = xref1[::self.stepSize]   # downsample, to match the data steps (here, keep evrey 5)

        print(xref1.shape)

        xs = self.Psi[:, 0]
        ys = self.Psi[:, 1]
        zs = self.Psi[:, 2]

        # normalize these to amplitude one?
        print('normalizing amplitudes of Psi in Python ...')
        xs /= np.max(np.abs(xs))
        ys /= np.max(np.abs(ys))
        zs /= np.max(np.abs(zs))

        # xs -= np.mean(xs)
        # ys -= np.mean(ys)
        # zs -= np.mean(zs)

        # xs /= np.std(xs)
        # ys /= np.std(ys)
        # zs /= np.std(zs)

        print(xs.shape)

        lim = 2000
        val = xref1[:lim]
        idx = self.IDX[:lim]

        plt.figure(figsize=[15, 3])

        plt.plot(xref1[:lim], color='black', label='Timeseries')
        # plt.plot(xs[:lim], linewidth=.5, label='$\psi_0$')
        # plt.plot(ys[:lim], linewidth=.5, label='$\psi_1$')
        # plt.plot(zs[:lim], linewidth=.5, label='$\psi_2$')

        plt.plot(xs[:lim], linewidth=.5, label='psi_0')
        plt.plot(ys[:lim], linewidth=.5, label='psi_1')
        plt.plot(zs[:lim], linewidth=.5, label='psi_2')

        plt.plot(idx / np.max(idx) + 1, linewidth=.8, label='IDX')

        plt.legend()

        # rightarrow causes an image error, when displayed in github!
        # plt.xlabel('Time $ \\rightarrow $')
        plt.xlabel('Time')
        plt.ylabel('Value')

        # plt.gca().autoscale(enable=True, axis='both', tight=None )
        # plt.gca().xaxis.set_ticklabels([])
        # plt.gca().yaxis.set_ticklabels([])

        plt.title('Example Timeseries and Manifold Projection')

        print('done')

        ###
        ### additional parsing, for color graphs
        ###
        import matplotlib

        cmap = matplotlib.cm.get_cmap('Spectral')

        r = xs[:lim]
        g = ys[:lim]
        b = zs[:lim]

        # prevent the jump in data value
        r[:self.H] = r[self.H]
        g[:self.H] = g[self.H]
        b[:self.H] = b[self.H]

        r -= np.min(r)
        r /= np.max(r)

        g -= np.min(g)
        g /= np.max(g)

        b -= np.min(b)
        b /= np.max(b)

        plt.figure(figsize=[15, 3])

        for i in range(lim - 1):
            col = [r[i], g[i], b[i]]
            plt.plot([i, i + 1], [val[i], val[i + 1]], color=col)

        plt.title('data, colored according to Psi (color three-vector)')
        plt.xlabel('Time')
        plt.ylabel('Value')

        plt.show()