import tensorflow as tf
import numpy as np
import gc
from scripts.model.model_lgm_single_step import LgmSingleStep


class LgmSingleStepNaive(LgmSingleStep):

    def predict_tf(self, X: tf.Tensor, delta_x: tf.Tensor, build_masks: bool = False):
        if self.normalize:
            X_norm = (X - self.mean) / tf.sqrt(self.var + self.epsilon)
        predictions = self.custom_model(X_norm if self.normalize else X)
        predictions = tf.cast(predictions, dtype=tf.float64)
        predictions_rolled = tf.roll(predictions, shift=1, axis=0)

        grads_reshaped, grads, _, _= self._get_dv_dx_tf(X)
        grads_rolled = tf.roll(grads, shift=1, axis=0)

        grads_rolled = tf.reshape(grads_rolled, (tf.shape(grads)[0], 1))
        delta_x = tf.reshape(delta_x, (tf.shape(delta_x)[0], 1))

        v = predictions_rolled + grads_rolled * delta_x

        if build_masks:
            idx_preds = tf.reshape(
                tf.range(0, tf.shape(X)[0], self.N, dtype=tf.int64), (-1, 1)
            )
            np_mask_v = tf.ones((tf.shape(X)[0], 1), dtype=tf.float64)
            np_mask_v = tf.tensor_scatter_nd_update(
                np_mask_v,
                tf.reshape(idx_preds, (-1, 1)),
                tf.zeros_like(idx_preds, dtype=tf.float64),
            )
            mask_v = np_mask_v
            mask_preds = 1 - np_mask_v
        else:
            mask_v = self._mask_v
            mask_preds = self._mask_preds

        v = v * mask_v + predictions * mask_preds

        return v, predictions, grads_reshaped
    
    def predict(self, 
        X:tf.Tensor, 
        delta_x:tf.Tensor,
        build_masks: bool = False,
        debug: bool = False
    ):
        if self.normalize:
            X_norm = (X - self.mean) / tf.sqrt(self.var + self.epsilon)
        predictions = self.custom_model(X_norm if self.normalize else X)
        if debug:
            print(f'Predictions shape: {predictions.shape}')
            print(f'Predictions: {predictions}')
        predictions = tf.cast(
            predictions, 
            dtype=tf.float64
        )
        predictions_rolled = tf.roll(
            predictions,
            shift = 1,
            axis = 0
        )
        grads_reshaped, grads, _, _= self._get_dv_dx(X)
        grads_rolled = tf.roll(
            grads,
            shift = 1,
            axis = 0
        )
        grads_rolled = tf.reshape(grads_rolled, (grads.shape[0], 1))
        delta_x = tf.reshape(delta_x, (delta_x.shape[0], 1))
        v = tf.math.add(
            predictions_rolled,
            tf.math.multiply(
                grads_rolled,
                delta_x
            )
        )
        if not build_masks:
            mask_v = self._mask_v
            mask_preds = self._mask_preds
        else:
            idx_preds = np.array(range(0, X.shape[0], self.N))
            np_mask_v = np.ones((X.shape[0], 1))
            np_mask_v[idx_preds] = 0
            mask_v = tf.convert_to_tensor(
                np_mask_v, 
                dtype = tf.float64
            )
            mask_preds = tf.abs(
                tf.convert_to_tensor(
                    np_mask_v,
                    dtype = tf.float64
                ) - 1)
        v = tf.math.add(
            tf.math.multiply(
                v,
                mask_v
            ),
            tf.math.multiply(
                predictions,
                mask_preds
            )
        )
        
        return v, predictions, grads_reshaped

    def predict_loop(
        self,
        X: tf.Tensor,
        delta_x: tf.Tensor,
        build_masks: bool = False,
        debug: bool = False,
    ):
        """_summary_

        Args:
            X (tf.Tensor): _description_

        Returns:
            _type_: _description_
        """
        predictions = self.custom_model(X)
        if debug:
            print(f"Predictions shape: {predictions.shape}")
            print(f"Predictions: {predictions}")
        predictions = tf.cast(predictions, dtype=tf.float64)
        # Get the gradients
        grads = self._get_dv_dx(X)[1]
        # Reshapes
        delta_x = tf.reshape(delta_x, (delta_x.shape[0], 1))
        # Calculate V
        grads_reshaped = tf.reshape(grads, (self._batch_size, self.N))
        predictions_reshaped = tf.reshape(predictions, (self._batch_size, self.N))
        delta_x_reshaped = tf.reshape(delta_x, (self._batch_size, self.N))
        v = np.zeros((self._batch_size, self.N))
        v[:, 0] = predictions_reshaped[:, 0]
        for i in range(1, self.N):
            v[:, i] = (
                predictions_reshaped[:, i - 1]
                + grads_reshaped[:, i - 1] * delta_x_reshaped[:, i]
            )
        v = tf.convert_to_tensor(np.reshape(v, (self._batch_size * self.N, 1)))

        return v, predictions

    def clear_memory(self):
        gc.collect()
