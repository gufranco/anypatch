from __future__ import annotations

ALPHABET = 256
NODES = 2 * ALPHABET - 1
BLOCKS = 2 * NODES
NONE = -1
BITS_PER_BYTE = 8


class FgkError(ValueError):
    pass


class Decoder:
    def __init__(self) -> None:
        self.weight = [0] * NODES
        self.parent = [NONE] * NODES
        self.left_child = [NONE] * NODES
        self.right_child = [NONE] * NODES
        self.left = [NONE] * NODES
        self.right = [NONE] * NODES
        self.block = [NONE] * NODES
        self.leader = [NONE] * BLOCKS
        self.next_free = [*range(1, BLOCKS), NONE]
        self.free_block = 0
        self.root = 0
        self.cursor = 0
        self.zeros = 0
        self.free_node = ALPHABET
        self.zero_count = ALPHABET + 2
        self.zero_exp = 0
        self.zero_rem = 0
        self.coded: list[int] = []
        self.factor()
        self.factor()
        for node in range(ALPHABET):
            self.right_child[node] = node + 1 if node < ALPHABET - 1 else NONE
            self.left_child[node] = node - 1 if node >= 1 else NONE

    def factor(self) -> None:
        self.zero_count -= 1
        self.zero_exp = max(self.zero_count.bit_length() - 1, 0)
        self.zero_rem = self.zero_count - (1 << self.zero_exp)

    def make_block(self, lead: int) -> int:
        made = self.free_block
        self.free_block = self.next_free[made]
        self.leader[made] = lead
        return made

    def release(self, block: int) -> None:
        self.next_free[block] = self.free_block
        self.free_block = block

    def index_bits(self) -> int:
        return self.zero_exp if self.zero_rem == 0 else self.zero_exp + 1

    def bit(self, value: int) -> bool:
        if self.weight[self.cursor] == 0:
            self.coded.append(value)
            return len(self.coded) >= self.index_bits()
        self.cursor = self.right_child[self.cursor] if value else self.left_child[self.cursor]
        if self.left_child[self.cursor] != NONE:
            return False
        return self.weight[self.cursor] != 0 or self.zero_count == 1

    def nth_zero(self, n: int) -> int:
        found = self.zeros
        for _ in range(n):
            if self.right_child[found] == NONE:
                break
            found = self.right_child[found]
        return found

    def symbol(self) -> int:
        element = self.cursor
        if self.weight[self.cursor] == 0:
            index = int("".join(str(b) for b in self.coded) or "0", 2)
            element = self.nth_zero(index)
        self.coded = []
        self.update(element)
        self.cursor = self.root
        return element

    def update(self, n: int) -> None:
        node = self.increase_zero(n) if self.weight[n] == 0 else n
        while node != self.root:
            self.move_right(node)
            self.promote(node)
            self.weight[node] += 1
            node = self.parent[node]
        self.weight[self.root] += 1

    def swap_into_parents(self, forward: int, back: int) -> None:
        old_forward, old_back = self.parent[forward], self.parent[back]
        forward_right = self.right_child[old_forward] == forward
        back_right = self.right_child[old_back] == back
        self.parent[forward], self.parent[back] = old_back, old_forward
        if forward_right:
            self.right_child[old_forward] = back
        else:
            self.left_child[old_forward] = back
        if back_right:
            self.right_child[old_back] = forward
        else:
            self.left_child[old_back] = forward

    def relink(self, forward: int, back: int) -> None:
        self.left[self.right[back]] = forward
        if self.left[forward] != NONE:
            self.right[self.left[forward]] = back
        after = self.right[forward]
        self.right[forward] = self.right[back]
        if after == back:
            self.right[back] = forward
        else:
            self.left[after] = back
            self.right[back] = after
        before = self.left[back]
        self.left[back] = self.left[forward]
        if before == forward:
            self.left[forward] = back
        else:
            self.right[before] = forward
            self.left[forward] = before

    def move_right(self, forward: int) -> None:
        back = self.leader[self.block[forward]]
        if forward == back or self.parent[forward] == back or self.weight[forward] == 0:
            return
        self.relink(forward, back)
        self.swap_into_parents(forward, back)
        self.leader[self.block[forward]] = forward

    def next_block(self, node: int) -> int:
        right = self.right[node]
        if self.weight[node] == self.weight[right] - 1 and right != self.root:
            return self.block[right]
        return self.make_block(node)

    def promote(self, node: int) -> None:
        if self.weight[node] == 0:
            return
        left, right, current = self.left[node], self.right[node], self.block[node]
        zero_child = self.left_child[node] != NONE and self.weight[self.left_child[node]] == 0
        if left == self.right_child[node] and zero_child:
            if self.weight[node] == self.weight[right] - 1 and right != self.root:
                self.release(current)
                self.block[node] = self.block[left] = self.block[right]
            return
        if left == self.zeros:
            return
        if self.block[left] == current:
            self.leader[current] = left
        else:
            self.release(current)
        self.block[node] = self.next_block(node)

    def last_zero(self, node: int) -> int:
        self.right_child[node] = NONE
        right = self.right[node]
        self.block[node] = self.block[right] if self.weight[right] == 1 else self.make_block(node)
        self.zeros = NONE
        return node

    def eliminate(self, node: int) -> None:
        self.factor()
        if self.left_child[node] == NONE:
            self.zeros = self.right_child[self.zeros]
            self.left_child[self.zeros] = NONE
        elif self.right_child[node] == NONE:
            self.right_child[self.left_child[node]] = NONE
        else:
            self.left_child[self.right_child[node]] = self.left_child[node]
            self.right_child[self.left_child[node]] = self.right_child[node]

    def splice_internal(self, zero: int, internal: int) -> None:
        self.left[self.right[internal]] = internal
        self.left_child[self.parent[zero]] = internal
        right = self.right[internal]
        self.block[internal] = (
            self.block[right] if self.weight[right] == 1 else self.make_block(internal)
        )

    def increase_zero(self, node: int) -> int:
        if self.zero_count == 1:
            return self.last_zero(node)
        zero, internal = self.zeros, self.free_node
        self.free_node += 1
        self.parent[internal], self.right[internal] = self.parent[zero], self.right[zero]
        self.weight[internal], self.right_child[internal], self.left[internal] = 0, node, node
        if zero == self.root:
            self.root = internal
            self.block[node] = self.make_block(node)
            self.block[internal] = self.make_block(internal)
        else:
            self.splice_internal(zero, internal)
            self.block[node] = self.block[internal]
        self.eliminate(node)
        self.left_child[internal] = self.zeros
        self.right[node], self.left[node], self.parent[node] = internal, self.zeros, internal
        self.left_child[node] = self.right_child[node] = NONE
        self.parent[self.zeros], self.right[self.zeros] = internal, node
        return node

    def decode(self, data: bytes, size: int) -> bytes:
        if size <= 0:
            raise FgkError("a secondary section cannot decode to an empty output")
        out = bytearray()
        pos = 0
        while len(out) < size:
            if pos == len(data):
                raise FgkError(
                    "the secondary section ends before its output is complete: end of input"
                )
            byte, pos = data[pos], pos + 1
            for shift in range(BITS_PER_BYTE):
                if self.bit(byte >> shift & 1):
                    out.append(self.symbol())
                    if len(out) == size:
                        break
        if pos != len(data):
            raise FgkError(f"the secondary section has {len(data) - pos} bytes after its output")
        return bytes(out)
