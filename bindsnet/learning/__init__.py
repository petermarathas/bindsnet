import torch

from ..utils import im2col_indices


def post_pre(conn, **kwargs):
	'''
	Simple STDP rule involving both pre- and post-synaptic spiking activity.
	'''
	if not 'kernel_size' in conn.__dict__:
		x_source, x_target = conn.source.x.unsqueeze(-1), conn.target.x.unsqueeze(0)
		s_source, s_target = conn.source.s.float().unsqueeze(-1), conn.target.s.float().unsqueeze(0)
		
		# Post-synaptic.
		conn.w += conn.nu_post * x_source * s_target
		# Pre-synaptic.
		conn.w -= conn.nu_pre * s_source * x_target

		# Bound weights.
		conn.w = torch.clamp(conn.w, conn.wmin, conn.wmax)
	else:
		out_channels, _, kernel_height, kernel_width = conn.w.size()
		padding, stride = conn.padding, conn.stride
		
		x_source = im2col_indices(conn.source.x, kernel_height, kernel_width, padding=padding, stride=stride)
		x_target = conn.target.x.permute(1, 2, 3, 0).reshape(out_channels, -1)
		s_source = im2col_indices(conn.source.s, kernel_height, kernel_width, padding=padding, stride=stride).float()
		s_target = conn.target.s.permute(1, 2, 3, 0).reshape(out_channels, -1).float()
		
		# Post-synaptic.
		post = (x_source @ s_target.t()).view(conn.w.size())
		if post.max() > 0:
			post = post / post.max()
		
		conn.w += conn.nu_post * post
		
		# Pre-synaptic.
		pre = (s_source @ x_target.t()).view(conn.w.size())
		if pre.max() > 0:
			pre = pre / pre.max()
		
		conn.w -= conn.nu_pre * pre

		# Bound weights.
		conn.w = torch.clamp(conn.w, conn.wmin, conn.wmax)

def hebbian(conn, **kwargs):
	'''
	Simple Hebbian learning rule. Pre- and post-synaptic updates are both positive.
	'''
	# Post-synaptic.
	conn.w += conn.nu_post * conn.source.x.unsqueeze(-1) * conn.target.s.float().unsqueeze(0)
	# Pre-synaptic.
	conn.w += conn.nu_pre * conn.source.s.float().unsqueeze(-1) * conn.target.x.unsqueeze(0)

	# Bound weights.
	conn.w = torch.clamp(conn.w, conn.wmin, conn.wmax)

def m_stdp(conn, **kwargs):
	'''
	Reward-modulated STDP. Adapted from
	`(Florian 2007) <https://florian.io/papers/2007_Florian_Modulated_STDP.pdf>`_.
	'''
	# Parse keyword arguments.
	try:
		reward = kwargs['reward']
	except KeyError:
		raise KeyError('function m_stdp requires a reward kwarg')
	
	a_plus = kwargs.get('a_plus', 1)
	a_minus = kwargs.get('a_plus', -1)
	
	# Get P^+ and P^- values (function of firing traces).
	p_plus = a_plus * conn.source.x.unsqueeze(-1)
	p_minus = a_minus * conn.target.x.unsqueeze(0)
	
	# Get pre- and post-synaptic spiking neurons.
	pre_fire = conn.source.s.float().unsqueeze(-1)
	post_fire = conn.target.s.float().unsqueeze(0)
	
	# Calculate point eligibility value.
	eligibility = p_plus * post_fire + pre_fire * p_minus
	
	# Compute weight update.
	conn.w += conn.nu * reward * eligibility
	
	# Bound weights.
	conn.w = torch.clamp(conn.w, conn.wmin, conn.wmax)
	
def m_stdp_et(conn, **kwargs):
	'''
	Reward-modulated STDP with eligibility trace. Adapted from
	`(Florian 2007) <https://florian.io/papers/2007_Florian_Modulated_STDP.pdf>`_.
	'''
	# Parse keyword arguments.
	try:
		reward = kwargs['reward']
	except KeyError:
		raise KeyError('function m_stdp_et requires a reward kwarg')
	
	a_plus = kwargs.get('a_plus', 1)
	a_minus = kwargs.get('a_plus', -1)
	
	# Get P^+ and P^- values (function of firing traces).
	conn.p_plus = -(conn.tc_plus * conn.p_plus) + a_plus * conn.source.x.unsqueeze(-1)
	conn.p_minus = -(conn.tc_minus * conn.p_minus) + a_minus * conn.target.x.unsqueeze(0)
	
	# Get pre- and post-synaptic spiking neurons.
	pre_fire = conn.source.s.float().unsqueeze(-1)
	post_fire = conn.target.s.float().unsqueeze(0)
	
	# Calculate value of eligibility trace.
	conn.e_trace += -(conn.tc_e_trace * conn.e_trace) + (conn.p_plus * post_fire + pre_fire * conn.p_minus)
	
	# Compute weight update.
	conn.w += conn.nu * reward * conn.e_trace
	
	# Bound weights.
	conn.w = torch.clamp(conn.w, conn.wmin, conn.wmax)

