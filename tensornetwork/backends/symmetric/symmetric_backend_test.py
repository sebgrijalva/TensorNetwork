import numpy as np
import pytest
from tensornetwork.backends.symmetric import symmetric_backend
from tensornetwork.backends.numpy import numpy_backend
from tensornetwork.block_sparse.charge import U1Charge, charge_equal, BaseCharge
from tensornetwork.block_sparse.index import Index
from tensornetwork.block_sparse import (tensordot, BlockSparseTensor, transpose,
                                        sqrt, ChargeArray, diag, trace, norm,
                                        eye, ones, zeros, randn, random, eigh,
                                        inv)

np_randn_dtypes = [np.float32, np.float16, np.float64]
np_dtypes = np_randn_dtypes + [np.complex64, np.complex128]
np_tensordot_dtypes = [np.float16, np.float64, np.complex128]


def get_tensor(R, num_charges, dtype=np.float64):
  Ds = np.random.randint(8, 12, R)
  charges = [
      BaseCharge(
          np.random.randint(-5, 6, (Ds[n], num_charges)),
          charge_types=[U1Charge] * num_charges) for n in range(R)
  ]
  flows = list(np.full(R, fill_value=False, dtype=np.bool))
  indices = [Index(charges[n], flows[n]) for n in range(R)]
  return BlockSparseTensor.random(indices=indices, dtype=dtype)


def get_square_matrix(num_charges, dtype=np.float64):
  D = np.random.randint(40, 60)
  charges = BaseCharge(
      np.random.randint(-5, 6, (D, num_charges)),
      charge_types=[U1Charge] * num_charges)

  flows = [False, True]
  indices = [Index(charges, flows[n]) for n in range(2)]
  return BlockSparseTensor.random(indices=indices, dtype=dtype)


def get_hermitian_matrix(num_charges, dtype=np.float64):
  D = np.random.randint(40, 60)
  charges = BaseCharge(
      np.random.randint(-5, 6, (D, num_charges)),
      charge_types=[U1Charge] * num_charges)

  flows = [False, True]
  indices = [Index(charges, flows[n]) for n in range(2)]
  A = BlockSparseTensor.random(indices=indices, dtype=dtype)
  return A + A.conj().T


def get_chargearray(num_charges, dtype=np.float64):
  D = np.random.randint(8, 12)
  charge = BaseCharge(
      np.random.randint(-5, 6, (D, num_charges)),
      charge_types=[U1Charge] * num_charges)
  flow = False
  index = Index(charge, flow)
  return ChargeArray.random(indices=[index], dtype=dtype)


def get_contractable_tensors(R1, R2, cont, dtype, num_charges):
  DsA = np.random.randint(5, 10, R1)
  DsB = np.random.randint(5, 10, R2)
  assert R1 >= cont
  assert R2 >= cont
  chargesA = [
      BaseCharge(
          np.random.randint(-5, 6, (DsA[n], num_charges)),
          charge_types=[U1Charge] * num_charges) for n in range(R1 - cont)
  ]
  commoncharges = [
      BaseCharge(
          np.random.randint(-5, 6, (DsA[n + R1 - cont], num_charges)),
          charge_types=[U1Charge] * num_charges) for n in range(cont)
  ]
  chargesB = [
      BaseCharge(
          np.random.randint(-5, 6, (DsB[n], num_charges)),
          charge_types=[U1Charge] * num_charges) for n in range(R2 - cont)
  ]
  #contracted indices
  indsA = np.random.choice(np.arange(R1), cont, replace=False)
  indsB = np.random.choice(np.arange(R2), cont, replace=False)

  flowsA = np.full(R1, False, dtype=np.bool)
  flowsB = np.full(R2, False, dtype=np.bool)
  flowsB[indsB] = True

  indicesA = [None for _ in range(R1)]
  indicesB = [None for _ in range(R2)]
  for n, iA in enumerate(indsA):
    indicesA[iA] = Index(commoncharges[n], flowsA[iA])
    indicesB[indsB[n]] = Index(commoncharges[n], flowsB[indsB[n]])
  compA = list(set(np.arange(R1)) - set(indsA))
  compB = list(set(np.arange(R2)) - set(indsB))

  for n, cA in enumerate(compA):
    indicesA[cA] = Index(chargesA[n], flowsA[cA])
  for n, cB in enumerate(compB):
    indicesB[cB] = Index(chargesB[n], flowsB[cB])

  indices_final = []
  for n in sorted(compA):
    indices_final.append(indicesA[n])
  for n in sorted(compB):
    indices_final.append(indicesB[n])
  A = BlockSparseTensor.random(indices=indicesA, dtype=dtype)
  B = BlockSparseTensor.random(indices=indicesB, dtype=dtype)
  return A, B, indsA, indsB


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R1, R2, cont", [(4, 4, 2), (4, 3, 3), (3, 4, 3)])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_tensordot(R1, R2, cont, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a, b, indsa, indsb = get_contractable_tensors(R1, R2, cont, dtype,
                                                num_charges)
  actual = backend.tensordot(a, b, (indsa, indsb))
  expected = tensordot(a, b, (indsa, indsb))
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


def test_gmres_not_implemented():
  backend = symmetric_backend.SymmetricBackend()
  with pytest.raises(NotImplementedError):
    backend.gmres(lambda x: x, np.ones((2)))


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_reshape(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  shape = a.shape
  partitions = np.append(
      np.append(
          0,
          np.sort(
              np.random.choice(
                  np.arange(1, R), np.random.randint(1, R), replace=False))), R)
  new_shape = tuple([
      np.prod(shape[partitions[n - 1]:partitions[n]])
      for n in range(1, len(partitions))
  ])
  actual = backend.shape_tuple(backend.reshape(a, new_shape))
  assert actual == new_shape


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_transpose(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  order = np.arange(R)
  np.random.shuffle(order)
  actual = backend.transpose(a, order)
  expected = transpose(a, order)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


def test_shape_concat():
  backend = symmetric_backend.SymmetricBackend()
  a = np.asarray((2 * np.ones((1, 3, 1))))
  b = np.asarray(np.ones((1, 2, 1)))
  expected = backend.shape_concat((a, b), axis=1)
  actual = np.array([[[2.0], [2.0], [2.0], [1.0], [1.0]]])
  np.testing.assert_allclose(expected, actual)


def test_shape_tensor():

  backend = symmetric_backend.SymmetricBackend()
  a = np.asarray(np.ones([2, 3, 4]))
  assert isinstance(backend.shape_tensor(a), tuple)
  actual = backend.shape_tensor(a)
  expected = np.array([2, 3, 4])
  np.testing.assert_allclose(expected, actual)


def test_shape_tuple():
  backend = symmetric_backend.SymmetricBackend()
  a = np.asarray(np.ones([2, 3, 4]))
  actual = backend.shape_tuple(a)
  assert actual == (2, 3, 4)


def test_shape_prod():
  backend = symmetric_backend.SymmetricBackend()
  a = np.array(2 * np.ones([1, 2, 3, 4]))
  actual = np.array(backend.shape_prod(a))
  assert actual == 2**24


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_sqrt(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  actual = backend.sqrt(a)
  expected = sqrt(a)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R1, R2", [(2, 2), (2, 3), (3, 3)])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_outer_product(R1, R2, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R1, num_charges, dtype)
  b = get_tensor(R2, num_charges, dtype)
  actual = backend.outer_product(a, b)
  expected = tensordot(a, b, 0)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_norm(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  assert backend.norm(a) == norm(a)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_eye(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  index = Index(
      BaseCharge(
          np.random.randint(-5, 6, (100, num_charges)),
          charge_types=[U1Charge] * num_charges), False)
  actual = backend.eye(index, dtype=dtype)
  expected = eye(index, dtype=dtype)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_eye_dtype(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  index = Index(
      BaseCharge(
          np.random.randint(-5, 6, (100, num_charges)),
          charge_types=[U1Charge] * num_charges), False)
  actual = backend.eye(index, dtype=dtype)
  assert actual.dtype == dtype


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_ones(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.ones(indices, dtype=dtype)
  expected = ones(indices, dtype=dtype)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_ones_dtype(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.ones(indices, dtype=dtype)
  assert actual.dtype == dtype


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_zeros(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.zeros(indices, dtype=dtype)
  expected = zeros(indices, dtype=dtype)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_zeros_dtype(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.zeros(indices, dtype=dtype)
  assert actual.dtype == dtype


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_randn(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.randn(indices, dtype=dtype, seed=10)
  np.random.seed(10)
  expected = randn(indices, dtype=dtype)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_randn_dtype(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.randn(indices, dtype=dtype, seed=10)
  assert actual.dtype == dtype


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_random_uniform(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.random_uniform(indices, dtype=dtype, seed=10)
  np.random.seed(10)
  expected = random(indices, dtype=dtype)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_random_uniform_dtype(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.random_uniform(indices, dtype=dtype, seed=10)
  assert actual.dtype == dtype


@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("dtype", [np.complex64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_randn_non_zero_imag(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.randn(indices, dtype=dtype, seed=10)
  assert np.linalg.norm(np.imag(actual.data)) != 0.0


@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("dtype", [np.complex64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_random_uniform_non_zero_imag(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  actual = backend.random_uniform(indices, dtype=dtype, seed=10)
  assert np.linalg.norm(np.imag(actual.data)) != 0.0


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_randn_seed(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  a = backend.randn(indices, dtype=dtype, seed=10)
  b = backend.randn(indices, dtype=dtype, seed=10)
  np.testing.assert_allclose(a.data, b.data)
  assert np.all([
      charge_equal(a._charges[n], b._charges[n])
      for n in range(len(a._charges))
  ])


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_random_uniform_seed(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  a = backend.random_uniform(indices, dtype=dtype, seed=10)
  b = backend.random_uniform(indices, dtype=dtype, seed=10)
  np.testing.assert_allclose(a.data, b.data)
  assert np.all([
      charge_equal(a._charges[n], b._charges[n])
      for n in range(len(a._charges))
  ])


@pytest.mark.parametrize("dtype", np_randn_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_random_uniform_boundaries(dtype, num_charges):
  np.random.seed(10)
  lb = 1.2
  ub = 4.8
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (10, num_charges)),
              charge_types=[U1Charge] * num_charges), False) for _ in range(R)
  ]
  a = backend.random_uniform(indices, seed=10, dtype=dtype)
  b = backend.random_uniform(indices, (lb, ub), seed=10, dtype=dtype)
  assert ((a.data >= 0).all() and (a.data <= 1).all() and
          (b.data >= lb).all() and (b.data <= ub).all())


@pytest.mark.parametrize(
    "dtype", [np.complex64, np.complex128, np.float64, np.float32, np.float16])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_conj(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  aconj = backend.conj(a)
  np.testing.assert_allclose(aconj.data, np.conj(a.data))


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_addition(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  b = BlockSparseTensor.random(a.sparse_shape)
  res = backend.addition(a, b)
  np.testing.assert_allclose(res.data, a.data + b.data)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_addition_raises(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  b = get_tensor(R + 1, num_charges, dtype)
  with pytest.raises(ValueError):
    backend.addition(a, b)

  shape = b.sparse_shape
  c = BlockSparseTensor.random([shape[n] for n in reversed(range(len(shape)))])
  with pytest.raises(ValueError):
    backend.addition(a, c)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_subtraction(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  b = BlockSparseTensor.random(a.sparse_shape)
  res = backend.subtraction(a, b)

  np.testing.assert_allclose(res.data, a.data - b.data)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("R", [2, 3, 4, 5])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_subbtraction_raises(R, dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  b = get_tensor(R + 1, num_charges, dtype)
  with pytest.raises(ValueError):
    backend.subtraction(a, b)
  shape = b.sparse_shape
  c = BlockSparseTensor.random([shape[n] for n in reversed(range(len(shape)))])
  with pytest.raises(ValueError):
    backend.subtraction(a, c)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_multiply(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  res = backend.multiply(a, 5.1)
  np.testing.assert_allclose(res.data, a.data * 5.1)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_multiply_raises(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  with pytest.raises(TypeError):
    backend.multiply(a, np.array([5.1]))


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_truediv(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  res = backend.divide(a, 5.1)
  np.testing.assert_allclose(res.data, a.data / 5.1)


@pytest.mark.parametrize("dtype", np_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_truediv_raises(dtype, num_charges):
  np.random.seed(10)
  R = 4
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(R, num_charges, dtype)
  with pytest.raises(TypeError):
    backend.divide(a, np.array([5.1]))


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_eigh(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  H = get_hermitian_matrix(num_charges, dtype)
  eta, U = backend.eigh(H)
  eta_ac, U_ac = eigh(H)
  np.testing.assert_allclose(eta.data, eta_ac.data)
  np.testing.assert_allclose(U.data, U_ac.data)
  assert charge_equal(eta._charges[0], eta_ac._charges[0])
  assert np.all([
      charge_equal(U._charges[n], U_ac._charges[n])
      for n in range(len(U._charges))
  ])


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_matrix_inv(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  H = get_hermitian_matrix(num_charges, dtype)
  Hinv = backend.inv(H)
  Hinv_ac = inv(H)
  np.testing.assert_allclose(Hinv_ac.data, Hinv.data)
  assert np.all([
      charge_equal(Hinv._charges[n], Hinv_ac._charges[n])
      for n in range(len(Hinv._charges))
  ])


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_matrix_inv_raises(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  H = get_tensor(3, num_charges, dtype)
  with pytest.raises(ValueError):
    backend.inv(H)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_broadcast_right_multiplication(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  Ds = [10, 30, 24]
  R = len(Ds)
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (Ds[n], num_charges)),
              charge_types=[U1Charge] * num_charges), False) for n in range(R)
  ]
  tensor1 = backend.randn(indices, dtype=dtype)
  tensor2 = ChargeArray.random(
      indices=[indices[-1].copy().flip_flow()], dtype=dtype)
  t1dense = tensor1.todense()
  t2dense = tensor2.todense()
  out = backend.broadcast_right_multiplication(tensor1, tensor2)
  dense = t1dense * t2dense
  np.testing.assert_allclose(out.todense(), dense)


def test_broadcast_right_multiplication_raises():
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  num_charges = 1
  Ds = [10, 30, 24]
  R = len(Ds)
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (Ds[n], num_charges)),
              charge_types=[U1Charge] * num_charges), False) for n in range(R)
  ]
  tensor1 = backend.randn(indices)
  tensor2 = ChargeArray.random(indices=indices)
  with pytest.raises(ValueError):
    backend.broadcast_right_multiplication(tensor1, tensor2)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_broadcast_left_multiplication(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  Ds = [10, 30, 24]
  R = len(Ds)
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (Ds[n], num_charges)),
              charge_types=[U1Charge] * num_charges), False) for n in range(R)
  ]

  tensor1 = ChargeArray.random(indices=[indices[0]], dtype=dtype)
  tensor2 = backend.randn(indices, dtype=dtype)
  t1dense = tensor1.todense()
  t2dense = tensor2.todense()
  out = backend.broadcast_left_multiplication(tensor1, tensor2)
  dense = np.reshape(t1dense, (10, 1, 1)) * t2dense
  np.testing.assert_allclose(out.todense(), dense)


def test_broadcast_left_multiplication_raises():
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  num_charges = 1
  Ds = [10, 30, 24]
  R = len(Ds)
  indices = [
      Index(
          BaseCharge(
              np.random.randint(-5, 6, (Ds[n], num_charges)),
              charge_types=[U1Charge] * num_charges), False) for n in range(R)
  ]

  tensor1 = ChargeArray.random(indices=indices)
  tensor2 = backend.randn(indices)
  with pytest.raises(ValueError):
    backend.broadcast_left_multiplication(tensor1, tensor2)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("num_charges", [1, 2])
def test_sparse_shape(dtype, num_charges):
  np.random.seed(10)
  Ds = [11, 12, 13]
  R = len(Ds)
  charges = [
      BaseCharge(
          np.random.randint(-5, 6, (Ds[n], num_charges)),
          charge_types=[U1Charge] * num_charges) for n in range(R)
  ]
  flows = list(np.full(R, fill_value=False, dtype=np.bool))
  indices = [Index(charges[n], flows[n]) for n in range(R)]
  a = BlockSparseTensor.random(indices=indices, dtype=dtype)
  backend = symmetric_backend.SymmetricBackend()
  for s1, s2 in zip(a.sparse_shape, backend.sparse_shape(a)):
    assert s1 == s2


#################################################################
# the following are sanity checks for eigsh_lanczos which do not
# really use block sparsity (all charges are identity charges)
#################################################################
@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_eigsh_valid_init_operator_with_shape_sanity_check(dtype):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  D = 16
  index = Index(U1Charge.random(D, 0, 0), True)
  indices = [index, index.copy().flip_flow()]

  a = BlockSparseTensor.random(indices, dtype=dtype)
  H = a + a.T.conj()

  def mv(vec, mat):
    return mat @ vec

  init = BlockSparseTensor.random([index], dtype=dtype)
  eta1, U1 = backend.eigsh_lanczos(mv, [H], init)
  v1 = np.reshape(U1[0].todense(), (D))
  v1 = v1 / sum(v1)

  eta2, U2 = np.linalg.eigh(H.todense())
  v2 = U2[:, 0]
  v2 = v2 / sum(v2)

  np.testing.assert_allclose(eta1[0], min(eta2))
  np.testing.assert_allclose(v1, v2)


def test_eigsh_small_number_krylov_vectors_sanity_check():
  np.random.seed(10)
  dtype = np.float64
  backend = symmetric_backend.SymmetricBackend()
  index = Index(U1Charge.random(2, 0, 0), True)
  indices = [index, index.copy().flip_flow()]

  H = BlockSparseTensor.random(indices, dtype=dtype)
  H.data = np.array([1, 2, 3, 4], dtype=np.float64)

  init = BlockSparseTensor.random([index], dtype=dtype)
  init.data = np.array([1, 1], dtype=np.float64)

  def mv(x, mat):
    return mat @ x

  eta, _ = backend.eigsh_lanczos(mv, [H], init, num_krylov_vecs=1)
  np.testing.assert_allclose(eta[0], 5)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_eigsh_lanczos_sanity_check_1(dtype):
  np.random.seed(10)
  D = 16
  backend = symmetric_backend.SymmetricBackend()
  index = Index(U1Charge.random(D, 0, 0), True)
  indices = [index, index.copy().flip_flow()]

  H = BlockSparseTensor.random(indices, dtype=dtype)
  H = H + H.conj().T

  init = BlockSparseTensor.random([index], dtype=dtype)

  def mv(x, mat):
    return mat @ x

  eta1, U1 = backend.eigsh_lanczos(mv, [H], init)
  eta2, U2 = np.linalg.eigh(H.todense())
  v1 = np.reshape(U1[0].todense(), (D))
  v1 = v1 / sum(v1)

  v2 = U2[:, 0]
  v2 = v2 / sum(v2)
  np.testing.assert_allclose(eta1[0], min(eta2))
  np.testing.assert_allclose(v1, v2)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_eigsh_lanczos_sanity_check_2(dtype):
  np.random.seed(10)
  D = 16
  backend = symmetric_backend.SymmetricBackend()
  index = Index(U1Charge.random(D, 0, 0), True)
  indices = [index, index.copy().flip_flow()]

  H = BlockSparseTensor.random(indices, dtype=dtype)
  H = H + H.conj().T

  def mv(x, mat):
    return mat @ x

  eta1, U1 = backend.eigsh_lanczos(
      mv, [H], shape=(H.sparse_shape[1].flip_flow(),), dtype=dtype)
  eta2, U2 = np.linalg.eigh(H.todense())
  v1 = np.reshape(U1[0].todense(), (D))
  v1 = v1 / sum(v1)

  v2 = U2[:, 0]
  v2 = v2 / sum(v2)

  np.testing.assert_allclose(eta1[0], min(eta2))
  np.testing.assert_allclose(v1, v2)


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
@pytest.mark.parametrize("numeig", [1, 2, 3, 4])
def test_eigsh_lanczos_reorthogonalize_sanity_check(dtype, numeig):
  np.random.seed(10)
  D = 24
  backend = symmetric_backend.SymmetricBackend()
  index = Index(U1Charge.random(D, 0, 0), True)
  indices = [index, index.copy().flip_flow()]

  H = BlockSparseTensor.random(indices, dtype=dtype)
  H = H + H.conj().T

  def mv(x, mat):
    return mat @ x

  eta1, U1 = backend.eigsh_lanczos(
      mv, [H],
      shape=(H.sparse_shape[1].flip_flow(),),
      dtype=dtype,
      numeig=numeig,
      num_krylov_vecs=D,
      reorthogonalize=True,
      ndiag=1,
      tol=10**(-12),
      delta=10**(-12))
  eta2, U2 = np.linalg.eigh(H.todense())

  np.testing.assert_allclose(eta1[0:numeig], eta2[0:numeig])
  for n in range(numeig):
    v2 = U2[:, n]
    v2 /= np.sum(v2)  #fix phases
    v1 = np.reshape(U1[n].todense(), (D))
    v1 /= np.sum(v1)

    np.testing.assert_allclose(v1, v2, rtol=10**(-5), atol=10**(-5))


#################################################################
# finished sanity checks
#################################################################


def test_eigsh_lanczos_raises():
  backend = symmetric_backend.SymmetricBackend()
  with pytest.raises(
      ValueError, match='`num_krylov_vecs` >= `numeig` required!'):
    backend.eigsh_lanczos(lambda x: x, numeig=10, num_krylov_vecs=9)
  with pytest.raises(
      ValueError,
      match="Got numeig = 2 > 1 and `reorthogonalize = False`. "
      "Use `reorthogonalize=True` for `numeig > 1`"):
    backend.eigsh_lanczos(lambda x: x, numeig=2, reorthogonalize=False)
  with pytest.raises(
      ValueError,
      match="if no `initial_state` is passed, then `shape` and"
      "`dtype` have to be provided"):
    backend.eigsh_lanczos(lambda x: x, shape=(10,), dtype=None)
  with pytest.raises(
      ValueError,
      match="if no `initial_state` is passed, then `shape` and"
      "`dtype` have to be provided"):
    backend.eigsh_lanczos(lambda x: x, shape=None, dtype=np.float64)
  with pytest.raises(
      ValueError,
      match="if no `initial_state` is passed, then `shape` and"
      "`dtype` have to be provided"):
    backend.eigsh_lanczos(lambda x: x)
  with pytest.raises(
      TypeError, match="Expected a `BlockSparseTensor`. Got <class 'list'>"):
    backend.eigsh_lanczos(lambda x: x, initial_state=[1, 2, 3])


@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_eigsh_valid_init_operator_with_shape(dtype):
  np.random.seed(100)
  backend = symmetric_backend.SymmetricBackend()
  np_backend = numpy_backend.NumPyBackend()
  D = 16
  index = Index(U1Charge.random(D, -1, 1), True)
  indices = [index, index.copy().flip_flow()]

  a = BlockSparseTensor.random(indices, dtype=dtype)
  H = a + a.T.conj()

  def mv(vec, mat):
    return mat @ vec

  init = BlockSparseTensor.random([index], dtype=dtype)
  # note: this will only find eigenvalues in the charge (0,0)
  # block of H because `init` only has non-zero values there.
  # To find eigen values in other sectors we need to support non-zero
  # divergence for block-sparse tensors
  eta1, U1 = backend.eigsh_lanczos(mv, [H], init)
  eta2, U2 = np_backend.eigsh_lanczos(mv, [H.todense()], init.todense())

  v1 = np.reshape(U1[0].todense(), (D))
  v1 = v1 / sum(v1)
  v1 /= np.linalg.norm(v1)
  v2 = np.reshape(U2[0], (D))
  v2 = v2 / sum(v2)
  v2[np.abs(v2) < 1E-12] = 0.0
  v2 /= np.linalg.norm(v2)

  np.testing.assert_allclose(eta1[0], min(eta2))
  np.testing.assert_allclose(v1, v2)


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
def test_diagflat(dtype, num_charges):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_tensor(3, num_charges, dtype)
  with pytest.raises(ValueError):
    backend.diagflat(a)
  b = get_chargearray(num_charges, dtype)
  expected = diag(b)
  actual = backend.diagflat(b)
  np.testing.assert_allclose(expected.data, actual.data)
  assert np.all([
      charge_equal(expected._charges[n], actual._charges[n])
      for n in range(len(actual._charges))
  ])


@pytest.mark.parametrize("dtype", np_tensordot_dtypes)
@pytest.mark.parametrize("num_charges", [1, 2])
@pytest.mark.parametrize("offset", [0, 1])
@pytest.mark.parametrize("axis1", range(0, 1))
@pytest.mark.parametrize("axis2", range(0, 1))
def test_trace(dtype, num_charges, offset, axis1, axis2):
  np.random.seed(10)
  backend = symmetric_backend.SymmetricBackend()
  a = get_square_matrix(num_charges, dtype)
  if offset != 0:
    with pytest.raises(NotImplementedError):
      actual = backend.trace(a, offset=offset, axis1=axis1, axis2=axis2)
  elif axis1 == axis2:
    with pytest.raises(ValueError):
      actual = backend.trace(a, offset=offset, axis1=axis1, axis2=axis2)
  else:
    actual = backend.trace(a, offset=offset, axis1=axis1, axis2=axis2)
    expected = trace(a, [axis1, axis2])
    np.testing.assert_allclose(actual.data, expected.data)


def test_pivot_not_implemented():
  backend = symmetric_backend.SymmetricBackend()
  with pytest.raises(NotImplementedError):
    backend.pivot(np.ones((2, 2)))
