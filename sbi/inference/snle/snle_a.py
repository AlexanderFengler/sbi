# This file is part of sbi, a toolkit for simulation-based inference. sbi is licensed
# under the Affero General Public License v3, see <https://www.gnu.org/licenses/>.

from __future__ import annotations
from typing import Callable, Optional, Union

import torch
from torch import Tensor, nn
from torch.utils.tensorboard import SummaryWriter

from sbi.inference.posterior import NeuralPosterior
from sbi.inference.snle.snle_base import LikelihoodEstimator
from sbi.utils.torchutils import get_default_device
from sbi.types import OneOrMore


class SNLE_A(LikelihoodEstimator):
    def __init__(
        self,
        simulator: Callable,
        prior,
        x_shape: Optional[torch.Size] = None,
        num_workers: int = 1,
        simulation_batch_size: int = 1,
        density_estimator: Union[str, nn.Module] = "maf",
        mcmc_method: str = "slice_np",
        device: Union[torch.device, str] = get_default_device(),
        logging_level: Union[int, str] = "WARNING",
        summary_writer: Optional[SummaryWriter] = None,
        show_progress_bars: bool = True,
        show_round_summary: bool = False,
    ):
        r"""Sequential Neural Likelihood [1].

        [1] Sequential Neural Likelihood: Fast Likelihood-free Inference with
        Autoregressive Flows_, Papamakarios et al., AISTATS 2019,
        https://arxiv.org/abs/1805.07226

        Args:
            simulator: A function that takes parameters $\theta$ and maps them to
                simulations, or observations, `x`, $\mathrm{sim}(\theta)\to x$. Any
                regular Python callable (i.e. function or class with `__call__` method)
                can be used.
            prior: A probability distribution that expresses prior knowledge about the
                parameters, e.g. which ranges are meaningful for them. Any
                object with `.log_prob()`and `.sample()` (for example, a PyTorch
                distribution) can be used.
            x_shape: Shape of a single simulation output $x$, has to be (1,N).
            num_workers: Number of parallel workers to use for simulations.
            simulation_batch_size: Number of parameter sets that the simulator
                maps to data x at once. If None, we simulate all parameter sets at the
                same time. If >= 1, the simulator has to process data of shape
                (simulation_batch_size, parameter_dimension).
            density_estimator: Either a string or a density estimation neural network
                that can `.log_prob()` and `.sample()`. If it is a string, use a pre-
                configured network of the provided type (one of nsf, maf, mdn, made).
            mcmc_method: If MCMC sampling is used, specify the method here: either of
                slice_np, slice, hmc, nuts.
            device: torch device on which to compute, e.g. cuda, cpu.
            logging_level: Minimum severity of messages to log. One of the strings
                INFO, WARNING, DEBUG, ERROR and CRITICAL.
            summary_writer: A `SummaryWriter` to control, among others, log
                file location (default is `<current working directory>/logs`.)
            show_progress_bars: Whether to show a progressbar during simulation and
                sampling.
            show_round_summary: Whether to show the validation loss and leakage after
                each round.
        """

        super().__init__(
            simulator=simulator,
            prior=prior,
            x_shape=x_shape,
            num_workers=num_workers,
            simulation_batch_size=simulation_batch_size,
            density_estimator=density_estimator,
            mcmc_method=mcmc_method,
            device=device,
            logging_level=logging_level,
            summary_writer=summary_writer,
            show_progress_bars=show_progress_bars,
            show_round_summary=show_round_summary,
        )

    def __call__(
        self,
        num_rounds: int,
        num_simulations_per_round: OneOrMore[int],
        x_o: Optional[Tensor] = None,
        batch_size: int = 50,
        learning_rate: float = 5e-4,
        validation_fraction: float = 0.1,
        stop_after_epochs: int = 20,
        max_num_epochs: Optional[int] = None,
        clip_max_norm: Optional[float] = 5.0,
        exclude_invalid_x: bool = True,
        discard_prior_samples: bool = False,
        retrain_from_scratch_each_round: bool = False,
    ) -> NeuralPosterior:
        r"""Run SNLE.

        Return posterior $p(\theta|x)$ after inference (possibly over several rounds).

        Args:
            num_rounds: Number of rounds to run. Each round consists of a simulation and
                training phase. `num_rounds=1` leads to a posterior $p(\theta|x)$ valid
                for _any_ $x$ (amortized), but requires many simulations.
                Alternatively, with `num_rounds>1` the inference returns a posterior
                $p(\theta|x_o)$ focused on a specific observation `x_o`, potentially
                requiring less simulations.
            num_simulations_per_round: Number of simulator calls per round.
            x_o: An observation that is only required when doing inference
                over multiple rounds. After the first round, `x_o` is used to guide the
                sampling so that the simulator is run with parameters that are likely
                for that `x_o`, i.e. they are sampled from the posterior obtained in the
                previous round $p(\theta|x_o)$.
            batch_size: Training batch size.
            learning_rate: Learning rate for Adam optimizer.
            validation_fraction: The fraction of data to use for validation.
            stop_after_epochs: The number of epochs to wait for improvement on the
                validation set before terminating training.
            max_num_epochs: Maximum number of epochs to run. If reached, we stop
                training even when the validation loss is still decreasing. If None, we
                train until validation loss increases (see also `stop_after_epochs`).
            clip_max_norm: Value at which to clip the total gradient norm in order to
                prevent exploding gradients. Use None for no clipping.
            exclude_invalid_x: Whether to exclude simulation outputs `x=NaN` or `x=±∞`
                during training. Expect errors, silent or explicit, when `False`.
            discard_prior_samples: Whether to discard samples simulated in round 1, i.e.
                from the prior. Training may be sped up by ignoring such less targeted
                samples.
            retrain_from_scratch_each_round: Whether to retrain the conditional density
                estimator for the posterior from scratch each round.

        Returns:
            Posterior $p(\theta|x_o)$ that can be sampled and evaluated.
        """
        return super().__call__(
            num_rounds=num_rounds,
            num_simulations_per_round=num_simulations_per_round,
            x_o=x_o,
            batch_size=batch_size,
            learning_rate=learning_rate,
            validation_fraction=validation_fraction,
            stop_after_epochs=stop_after_epochs,
            max_num_epochs=max_num_epochs,
            clip_max_norm=clip_max_norm,
            exclude_invalid_x=exclude_invalid_x,
            discard_prior_samples=discard_prior_samples,
            retrain_from_scratch_each_round=retrain_from_scratch_each_round,
        )