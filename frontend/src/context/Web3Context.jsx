import React, { createContext, useContext, useState, useEffect } from 'react';

export const Web3Context = createContext(null);

export const SUPPORTED_NETWORKS = {
  1337: {
    name: 'Hardhat Local EVM',
    chainIdHex: '0x539',
    currency: 'ETH',
    rpcUrl: 'http://127.0.0.1:8545',
    explorer: 'http://127.0.0.1:8545'
  },
  31337: {
    name: 'Hardhat Node (31337)',
    chainIdHex: '0x7a69',
    currency: 'ETH',
    rpcUrl: 'http://127.0.0.1:8545',
    explorer: 'http://127.0.0.1:8545'
  },
  80002: {
    name: 'Polygon Amoy Testnet',
    chainIdHex: '0x13882',
    currency: 'POL',
    rpcUrl: 'https://rpc-amoy.polygon.technology',
    explorer: 'https://amoy.polygonscan.com'
  },
  11155111: {
    name: 'Ethereum Sepolia Testnet',
    chainIdHex: '0xaa36a7',
    currency: 'SEP',
    rpcUrl: 'https://rpc.sepolia.org',
    explorer: 'https://sepolia.etherscan.io'
  }
};

export function Web3Provider({ children }) {
  const [account, setAccount] = useState(null);
  const [chainId, setChainId] = useState(1337);
  const [balance, setBalance] = useState('100.00');
  const [isConnected, setIsConnected] = useState(false);
  const [isSimulated, setIsSimulated] = useState(false);
  const [isMetaMaskInstalled, setIsMetaMaskInstalled] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.ethereum) {
      setIsMetaMaskInstalled(true);

      // Check if already connected
      window.ethereum.request({ method: 'eth_accounts' })
        .then(accounts => {
          if (accounts && accounts.length > 0) {
            handleAccountChanged(accounts[0]);
          }
        })
        .catch(err => console.warn('Web3 accounts check error:', err));

      // Listen to events
      window.ethereum.on('accountsChanged', (accounts) => {
        if (accounts.length > 0) {
          handleAccountChanged(accounts[0]);
        } else {
          disconnect();
        }
      });

      window.ethereum.on('chainChanged', (hexChainId) => {
        const id = parseInt(hexChainId, 16);
        setChainId(id);
      });
    }
  }, []);

  const handleAccountChanged = async (addr) => {
    setAccount(addr);
    setIsConnected(true);
    setIsSimulated(false);
    setError(null);

    // Fetch balance
    if (window.ethereum) {
      try {
        const balHex = await window.ethereum.request({
          method: 'eth_getBalance',
          params: [addr, 'latest']
        });
        const balWei = parseInt(balHex, 16);
        const balEth = (balWei / 1e18).toFixed(4);
        setBalance(balEth);

        const currentChainHex = await window.ethereum.request({ method: 'eth_chainId' });
        setChainId(parseInt(currentChainHex, 16));
      } catch (e) {
        console.warn('Balance fetch error:', e);
      }
    }
  };

  const connectMetaMask = async () => {
    setError(null);
    if (!window.ethereum) {
      setError('MetaMask is not installed. Please install MetaMask or use Simulated Hardhat Wallet.');
      return false;
    }

    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      if (accounts && accounts.length > 0) {
        await handleAccountChanged(accounts[0]);
        return true;
      }
    } catch (err) {
      console.error('MetaMask connection error:', err);
      setError(err.message || 'MetaMask connection rejected');
      return false;
    }
    return false;
  };

  const connectSimulated = (customAddress = null) => {
    // Connect simulated local Hardhat authorized wallet
    const demoAddr = customAddress || '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65';
    setAccount(demoAddr);
    setChainId(1337);
    setBalance('100.00');
    setIsConnected(true);
    setIsSimulated(true);
    setError(null);
    return true;
  };

  const switchNetwork = async (targetChainId) => {
    const net = SUPPORTED_NETWORKS[targetChainId];
    if (!net) return;

    if (isSimulated || !window.ethereum) {
      setChainId(targetChainId);
      return;
    }

    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: net.chainIdHex }]
      });
      setChainId(targetChainId);
    } catch (switchError) {
      // Chain not added to metamask, prompt add
      if (switchError.code === 4902) {
        try {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: net.chainIdHex,
              chainName: net.name,
              nativeCurrency: { name: net.currency, symbol: net.currency, decimals: 18 },
              rpcUrls: [net.rpcUrl],
              blockExplorerUrls: [net.explorer]
            }]
          });
          setChainId(targetChainId);
        } catch (addError) {
          console.error('Failed to add network to MetaMask:', addError);
          setError('Failed to add network to MetaMask');
        }
      } else {
        console.error('Failed to switch network:', switchError);
        setError('Failed to switch network in MetaMask');
      }
    }
  };

  const disconnect = () => {
    setAccount(null);
    setIsConnected(false);
    setIsSimulated(false);
    setError(null);
  };

  const networkName = SUPPORTED_NETWORKS[chainId]?.name || `Chain ${chainId}`;
  const currency = SUPPORTED_NETWORKS[chainId]?.currency || 'ETH';

  return (
    <Web3Context.Provider value={{
      account,
      chainId,
      balance,
      currency,
      isConnected,
      isSimulated,
      isMetaMaskInstalled,
      networkName,
      error,
      connectMetaMask,
      connectSimulated,
      switchNetwork,
      disconnect
    }}>
      {children}
    </Web3Context.Provider>
  );
}

export function useWeb3Wallet() {
  const context = useContext(Web3Context);
  if (!context) {
    throw new Error('useWeb3Wallet must be used within a Web3Provider');
  }
  return context;
}
