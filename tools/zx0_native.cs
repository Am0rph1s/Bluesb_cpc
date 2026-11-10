using System;
using System.IO;
using System.Collections.Generic;

namespace ZX0
{
    public sealed class Block
    {
        public int bits;
        public int index;
        public int offset;
        public Block chain;

        public Block(int bits, int index, int offset, Block chain)
        {
            this.bits = bits;
            this.index = index;
            this.offset = offset;
            this.chain = chain;
        }
    }

    public static class Program
    {
        const int INITIAL_OFFSET = 1;
        const int MAX_OFFSET_ZX0 = 32640;
        const int MAX_OFFSET_ZX7 = 2176;

        static int EliasGammaBits(int value)
        {
            int bits = 1;
            while (value > 1)
            {
                value >>= 1;
                bits += 2;
            }
            return bits;
        }

        static int OffsetCeiling(int index, int offsetLimit)
        {
            int limit = index < offsetLimit ? index : offsetLimit;
            return limit < INITIAL_OFFSET ? INITIAL_OFFSET : limit;
        }

        static Block Optimize(byte[] inputData, int inputSize, int skip, int offsetLimit)
        {
            int maxOffset = OffsetCeiling(inputSize - 1, offsetLimit);
            if (maxOffset < INITIAL_OFFSET) maxOffset = INITIAL_OFFSET;

            Block[] lastLiteral = new Block[maxOffset + 1];
            Block[] lastMatch = new Block[maxOffset + 1];
            Block[] optimal = new Block[inputSize];
            int[] matchLength = new int[maxOffset + 1];
            int[] bestLength = new int[inputSize];

            if (inputSize > 2 + skip && 2 < bestLength.Length)
            {
                bestLength[2] = 2;
            }

            Block startBlock = new Block(-1, skip - 1, INITIAL_OFFSET, null);
            lastMatch[INITIAL_OFFSET] = startBlock;

            for (int index = skip; index < inputSize; index++)
            {
                int currentMaxOffset = OffsetCeiling(index, offsetLimit);
                int bestLenSize = 2;

                for (int offset = INITIAL_OFFSET; offset <= currentMaxOffset; offset++)
                {
                    if (index >= offset && inputData[index] == inputData[index - offset])
                    {
                        int matchLen = matchLength[offset] + 1;

                        if (lastLiteral[offset] != null)
                        {
                            int length = index - lastLiteral[offset].index;
                            if (length > 0)
                            {
                                int bits = lastLiteral[offset].bits + 1 + EliasGammaBits(length);
                                Block newBlock = new Block(bits, index, offset, lastLiteral[offset]);
                                lastMatch[offset] = newBlock;
                                if (optimal[index] == null || optimal[index].bits > bits)
                                    optimal[index] = newBlock;
                            }
                        }

                        matchLength[offset] = matchLen;

                        if (matchLen > 1)
                        {
                            if (bestLenSize < matchLen)
                            {
                                Block prevOptimal = optimal[index - bestLength[bestLenSize]];
                                if (prevOptimal != null)
                                {
                                    int bits = prevOptimal.bits + EliasGammaBits(bestLength[bestLenSize] - 1);
                                    while (bestLenSize < matchLen)
                                    {
                                        bestLenSize++;
                                        if (index - bestLenSize >= skip - 1)
                                        {
                                            Block prevOptimal2 = optimal[index - bestLenSize];
                                            if (prevOptimal2 != null)
                                            {
                                                int bits2 = prevOptimal2.bits + EliasGammaBits(bestLenSize - 1);
                                                if (bits2 <= bits)
                                                {
                                                    bestLength[bestLenSize] = bestLenSize;
                                                    bits = bits2;
                                                }
                                                else
                                                {
                                                    bestLength[bestLenSize] = bestLength[bestLenSize - 1];
                                                }
                                            }
                                            else
                                            {
                                                bestLength[bestLenSize] = bestLength[bestLenSize - 1];
                                            }
                                        }
                                        else
                                        {
                                            bestLength[bestLenSize] = bestLength[bestLenSize - 1];
                                        }
                                    }
                                }
                                else
                                {
                                    while (bestLenSize < matchLen)
                                    {
                                        bestLenSize++;
                                        bestLength[bestLenSize] = bestLength[bestLenSize - 1];
                                    }
                                }
                            }

                            int optLength = bestLength[matchLen];
                            if (index - optLength >= skip - 1 && optimal[index - optLength] != null)
                            {
                                int offsetMsb = (offset - 1) / 128 + 1;
                                int bits = optimal[index - optLength].bits + 1 + EliasGammaBits(offsetMsb) + 8 + EliasGammaBits(optLength - 1);

                                if (lastMatch[offset] == null || lastMatch[offset].index != index || lastMatch[offset].bits > bits)
                                {
                                    Block newBlock = new Block(bits, index, offset, optimal[index - optLength]);
                                    lastMatch[offset] = newBlock;
                                    if (optimal[index] == null || optimal[index].bits > bits)
                                        optimal[index] = newBlock;
                                }
                            }
                        }
                    }
                    else
                    {
                        matchLength[offset] = 0;
                        if (lastMatch[offset] != null)
                        {
                            Block prevBlock = lastMatch[offset];
                            int length = index - prevBlock.index;
                            if (length > 0)
                            {
                                int bits = prevBlock.bits + 1 + EliasGammaBits(length) + length * 8;
                                Block newBlock = new Block(bits, index, 0, prevBlock);
                                lastLiteral[offset] = newBlock;
                                if (optimal[index] == null || optimal[index].bits > bits)
                                    optimal[index] = newBlock;
                            }
                        }
                    }
                }
            }

            if (inputSize > skip)
            {
                if (optimal[inputSize - 1] == null)
                {
                    int literalLen = inputSize - skip;
                    int literalBits = startBlock.bits + 1 + EliasGammaBits(literalLen) + literalLen * 8;
                    optimal[inputSize - 1] = new Block(literalBits, inputSize - 1, 0, startBlock);
                }
                return optimal[inputSize - 1];
            }
            return null;
        }

        sealed class BitWriter
        {
            public List<byte> output = new List<byte>();
            public int bitMask = 0;
            public int bitIndex = -1;
            public bool backtrack = true;
            public bool backwardsMode;
            public bool invertMode;

            public BitWriter(bool backwardsMode, bool invertMode)
            {
                this.backwardsMode = backwardsMode;
                this.invertMode = invertMode;
            }

            public void WriteByte(int value)
            {
                output.Add((byte)value);
            }

            public void WriteBit(int value)
            {
                if (backtrack)
                {
                    if (value != 0)
                    {
                        output[output.Count - 1] |= 1;
                    }
                    backtrack = false;
                }
                else
                {
                    if (bitMask == 0)
                    {
                        bitMask = 128;
                        bitIndex = output.Count;
                        WriteByte(0);
                    }
                    if (value != 0)
                    {
                        output[bitIndex] |= (byte)bitMask;
                    }
                    bitMask >>= 1;
                }
            }

            public void WriteInterlacedEliasGamma(int value)
            {
                int i = 2;
                while (i <= value)
                {
                    i <<= 1;
                }
                i >>= 1;

                while (true)
                {
                    i >>= 1;
                    if (i == 0) break;
                    WriteBit(backwardsMode ? 1 : 0);
                    bool bit = (value & i) != 0;
                    WriteBit((invertMode ? !bit : bit) ? 1 : 0);
                }

                WriteBit(backwardsMode ? 0 : 1);
            }
        }

        static byte[] Compress(Block optimalEndBlock, byte[] inputData, int inputSize, int skip, bool backwardsMode, bool invertMode)
        {
            if (optimalEndBlock == null) return new byte[0];

            BitWriter writer = new BitWriter(backwardsMode, invertMode);

            List<Block> path = new List<Block>();
            Block curr = optimalEndBlock;
            while (curr != null && curr.index >= skip)
            {
                path.Add(curr);
                curr = curr.chain;
            }
            path.Reverse();

            if (path.Count == 0) return new byte[0];

            int lastOffset = INITIAL_OFFSET;

            for (int i = 0; i < path.Count; i++)
            {
                Block currentBlock = path[i];
                int prevIndex = (i > 0) ? path[i - 1].index : (skip - 1);
                int length = currentBlock.index - prevIndex;
                if (length <= 0 && i > 0) continue;

                if (currentBlock.offset == 0)
                {
                    // Literals
                    writer.WriteBit(0);
                    writer.WriteInterlacedEliasGamma(length);
                    for (int j = 0; j < length; j++)
                    {
                        writer.WriteByte(inputData[prevIndex + 1 + j]);
                    }
                }
                else if (currentBlock.offset == lastOffset)
                {
                    // Copy from last offset
                    writer.WriteBit(0);
                    writer.WriteInterlacedEliasGamma(length);
                }
                else
                {
                    // Copy from new offset
                    writer.WriteBit(1);
                    int offsetMsb = (currentBlock.offset - 1) / 128 + 1;
                    writer.WriteInterlacedEliasGamma(offsetMsb);
                    int offsetLsb = (currentBlock.offset - 1) % 128;
                    int byteVal = backwardsMode ? (offsetLsb << 1) : ((127 - offsetLsb) << 1);
                    writer.WriteByte(byteVal);
                    writer.backtrack = true;
                    writer.WriteInterlacedEliasGamma(length - 1);
                    lastOffset = currentBlock.offset;
                }
            }

            // End marker
            writer.WriteBit(1);
            writer.WriteInterlacedEliasGamma(256);

            return writer.output.ToArray();
        }

        public static int Main(string[] args)
        {
            bool classic = false;
            bool quick = false;
            bool backwards = false;
            int skip = 0;
            string inputPath = null;
            string outputPath = null;

            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "-c" || args[i] == "--classic") classic = true;
                else if (args[i] == "-q" || args[i] == "--quick") quick = true;
                else if (args[i] == "-b" || args[i] == "--backwards") backwards = true;
                else if (args[i] == "--skip" && i + 1 < args.Length)
                {
                    skip = int.Parse(args[++i]);
                }
                else if (inputPath == null) inputPath = args[i];
                else if (outputPath == null) outputPath = args[i];
            }

            if (inputPath == null || outputPath == null)
            {
                Console.Error.WriteLine("Usage: zx0_native [-c] [-q] [-b] [--skip N] <input> <output>");
                return 1;
            }

            byte[] inputData = File.ReadAllBytes(inputPath);
            if (inputData.Length == 0)
            {
                File.WriteAllBytes(outputPath, new byte[0]);
                return 0;
            }

            if (backwards)
            {
                Array.Reverse(inputData);
            }

            int offsetLimit = quick ? MAX_OFFSET_ZX7 : MAX_OFFSET_ZX0;
            Block optimal = Optimize(inputData, inputData.Length, skip, offsetLimit);
            byte[] output = Compress(optimal, inputData, inputData.Length, skip, backwards, !classic);

            if (backwards)
            {
                Array.Reverse(output);
            }

            File.WriteAllBytes(outputPath, output);
            return 0;
        }
    }
}
